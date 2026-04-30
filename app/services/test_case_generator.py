import json
import logging
from uuid import UUID

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from langchain_gigachat.chat_models import GigaChat

from app.config import settings

logger = logging.getLogger(__name__)


class TestCaseDraft(BaseModel):
    """Pydantic model for LLM output validation."""
    title: str = Field(description="Test case title")
    preconditions: str = Field(description="Preconditions for the test")
    steps: list[dict] = Field(description="List of {step, expected} dicts")


GENERATE_TESTCASE_PROMPT = """Ты — senior QA-инженер. Сгенерируй тест-кейс на основе user story.

User Story:
{user_story}

Верни JSON с полями:
- title: название тест-кейса (краткое, на русском)
- preconditions: предусловия (на русском)
- steps: список объектов {{"step": "действие", "expected": "ожидаемый результат"}}

Максимум 8 шагов. Ответь ТОЛЬКО валидным JSON без markdown обёрток."""


class TestCaseGeneratorService:
    def __init__(self) -> None:
        self._llm: GigaChat | None = None

    def _get_llm(self) -> GigaChat:
        if self._llm is None:
            credentials = settings.llm_api_key.get_secret_value()
            self._llm = GigaChat(
                credentials=credentials,
                verify_ssl_certs=False,
                model=settings.llm_model_name,
                temperature=0.3,
                max_tokens=2048,
            )
        return self._llm

    async def generate(self, user_story: str) -> dict:
        """Generate a test case draft from a user story."""
        llm = self._get_llm()

        prompt = GENERATE_TESTCASE_PROMPT.format(user_story=user_story)
        chat_prompt = ChatPromptTemplate.from_messages([("user", prompt)])
        chain = chat_prompt | llm | JsonOutputParser(pydantic_object=TestCaseDraft)

        try:
            result = await chain.ainvoke({})
            return result
        except json.JSONDecodeError as e:
            logger.warning("LLM returned invalid JSON: %s", e)
            return {
                "title": "Generated Test Case (parsing failed)",
                "preconditions": "Unable to parse LLM response",
                "steps": [{"step": "Review user story manually", "expected": "Test case created manually"}],
            }
        except Exception as e:
            logger.warning("LLM call failed: %s", e)
            return {
                "title": "Generated Test Case (LLM unavailable)",
                "preconditions": "LLM service unavailable",
                "steps": [{"step": "Retry later", "expected": "Test case generated successfully"}],
            }