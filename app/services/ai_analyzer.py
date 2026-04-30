import hashlib
import json
import logging
from enum import Enum

import asyncio
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_gigachat.chat_models import GigaChat
from pydantic import BaseModel, Field

from app.config import settings
from app.models.entities import AIAnalysis, TestResult
from app.repositories.ai import AIRepository
from app.services.embeddings import EmbeddingService
from app.services.ai_workflow import AnalysisState, build_analysis_workflow


logger = logging.getLogger(__name__)


class FailureCategory(str, Enum):
    REAL_DEFECT = "real_defect"
    FLAKY = "flaky"
    INFRASTRUCTURE = "infrastructure"


class AnalysisResult(BaseModel):
    category: FailureCategory
    probability: float = Field(ge=0.0, le=1.0)
    short_cause: str = Field(max_length=300)
    next_steps: list[str] = Field(max_length=6)


ANALYSIS_PROMPT = """Ты — senior QA-инженер. Проанализируй ошибку автотеста и верни JSON:
- category: "real_defect" | "flaky" | "infrastructure"
- probability: 0..1
- short_cause: описание до 300 символов
- next_steps: список 1-6 действий

Ошибка:
{error_message}

Stack trace:
{stack_trace}
"""


class AIAnalyzerService:
    def __init__(
        self,
        ai_repo: AIRepository,
        embedding_service: EmbeddingService,
    ) -> None:
        self._ai_repo = ai_repo
        self._embedding_service = embedding_service
        self._llm: GigaChat | None = None
        self._workflow = self._build_workflow()

    def _get_llm(self) -> GigaChat:
        if self._llm is None:
            credentials = settings.llm_api_key.get_secret_value()
            self._llm = GigaChat(
                credentials=credentials,
                verify_ssl_certs=False,
                model=settings.llm_model_name,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
            )
        return self._llm

    def _compute_hash(self, error_message: str, stack_trace: str | None) -> str:
        payload = f"{error_message}|{stack_trace}"
        return hashlib.sha256(payload.encode()).hexdigest()

    async def _ask_with_retries(self, prompt: str, max_retries: int = 3) -> AnalysisResult | None:
        llm = self._get_llm()
        chat_prompt = ChatPromptTemplate.from_messages([("user", prompt)])
        chain = chat_prompt | llm | JsonOutputParser(pydantic_object=AnalysisResult)

        for attempt in range(max_retries):
            try:
                result = await chain.ainvoke({})
                return result
            except json.JSONDecodeError as e:
                logger.warning("LLM returned invalid JSON (attempt %d): %s", attempt + 1, e)
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
            except Exception as e:
                logger.warning("LLM call failed (attempt %d): %s", attempt + 1, e)
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
        return None

    def _build_workflow(self):
        async def compute_embedding(state: AnalysisState) -> AnalysisState:
            embedding = await self._embedding_service.encode(state["error_text"])
            return {"embedding": embedding}

        async def check_duplicate(state: AnalysisState) -> AnalysisState:
            nearest = await self._ai_repo.find_nearest(state["embedding"])
            if nearest is not None:
                logger.info(f"Found similar analysis {nearest.id} for result {state.get('result_id', 'unknown')}")
                return {
                    "duplicate_found": True,
                    "duplicate_analysis_id": str(nearest.id),
                    "category": nearest.category,
                    "probability": nearest.probability,
                    "short_cause": nearest.short_cause,
                    "suggestion": nearest.suggestion,
                }
            return {"duplicate_found": False}

        async def classify_failure(state: AnalysisState) -> AnalysisState:
            prompt = ANALYSIS_PROMPT.format(
                error_message=state["error_text"],
                stack_trace=state.get("stack_trace", "")[:2000],
            )
            analysis_result = await self._ask_with_retries(prompt)

            if analysis_result is None:
                return {
                    "category": FailureCategory.INFRASTRUCTURE.value,
                    "probability": 0.1,
                    "short_cause": "Analysis failed, treating as infrastructure issue",
                    "suggestion": "Check infrastructure and retry",
                }
            return {
                "category": analysis_result.category.value,
                "probability": analysis_result.probability,
                "short_cause": analysis_result.short_cause,
                "suggestion": "\n".join(f"- {s}" for s in analysis_result.next_steps),
            }

        async def build_recommendation(state: AnalysisState) -> AnalysisState:
            return {
                "llm_model": settings.llm_model_name,
                "prompt_hash": self._compute_hash(state["error_text"], state.get("stack_trace")),
            }

        return build_analysis_workflow(
            compute_embedding_fn=compute_embedding,
            check_duplicate_fn=check_duplicate,
            classify_failure_fn=classify_failure,
            build_recommendation_fn=build_recommendation,
        )

    async def analyze(self, result: TestResult) -> AIAnalysis:
        error_text = result.error_message or ""
        stack_text = result.stack_trace or ""

        initial_state: AnalysisState = {
            "error_text": error_text,
            "stack_trace": stack_text,
            "embedding": [],
            "duplicate_found": False,
            "duplicate_analysis_id": None,
            "category": "",
            "probability": 0.0,
            "short_cause": "",
            "suggestion": "",
            "llm_model": "",
            "prompt_hash": "",
            "result_id": str(result.id),
        }

        final_state = await self._workflow.ainvoke(initial_state)

        if final_state.get("duplicate_found") and final_state.get("duplicate_analysis_id"):
            from uuid import UUID as _UUID
            existing = await self._ai_repo.get(_UUID(final_state["duplicate_analysis_id"]))
            if existing is not None:
                return existing

        if not final_state.get("category"):
            return AIAnalysis(
                result_id=result.id,
                category=FailureCategory.INFRASTRUCTURE.value,
                probability=0.1,
                short_cause="Analysis failed, treating as infrastructure issue",
                suggestion="Check infrastructure and retry",
                llm_model=settings.llm_model_name,
                prompt_hash=self._compute_hash(error_text, stack_text),
                error_embedding=final_state.get("embedding", []),
            )

        analysis = AIAnalysis(
            result_id=result.id,
            category=final_state["category"],
            probability=final_state["probability"],
            short_cause=final_state["short_cause"],
            suggestion=final_state["suggestion"],
            llm_model=final_state["llm_model"],
            prompt_hash=final_state["prompt_hash"],
            error_embedding=final_state.get("embedding", []),
        )

        saved = await self._ai_repo.save(analysis)
        return saved