"""Test AI workflow graph structure and compilation."""

import pytest


def test_workflow_compiles_successfully():
    """Verify the LangGraph StateGraph compiles without errors."""
    from app.services.ai_workflow import build_analysis_workflow

    async def dummy_compute(state):
        return {"embedding": [0.1] * 768}

    async def dummy_check(state):
        return {"duplicate_found": False}

    async def dummy_classify(state):
        return {
            "category": "infrastructure",
            "probability": 0.5,
            "short_cause": "test",
            "suggestion": "test",
        }

    async def dummy_recommend(state):
        return {"llm_model": "test", "prompt_hash": "abc"}

    workflow = build_analysis_workflow(
        compute_embedding_fn=dummy_compute,
        check_duplicate_fn=dummy_check,
        classify_failure_fn=dummy_classify,
        build_recommendation_fn=dummy_recommend,
    )

    assert workflow is not None


def test_workflow_has_expected_nodes():
    """Verify the workflow graph has the expected node names."""
    from app.services.ai_workflow import build_analysis_workflow

    async def dummy_fn(state):
        return {}

    workflow = build_analysis_workflow(
        compute_embedding_fn=dummy_fn,
        check_duplicate_fn=dummy_fn,
        classify_failure_fn=dummy_fn,
        build_recommendation_fn=dummy_fn,
    )

    node_names = list(workflow.nodes.keys()) if hasattr(workflow, "nodes") else []
    assert "compute_embedding" in node_names or len(node_names) >= 4


@pytest.mark.asyncio
async def test_workflow_routes_duplicate_to_end():
    """Verify that when duplicate is found, workflow routes to END (skips classify)."""
    from app.services.ai_workflow import build_analysis_workflow, AnalysisState

    call_order = []

    async def track_compute(state):
        call_order.append("compute_embedding")
        return {"embedding": [0.1] * 768}

    async def track_check(state):
        call_order.append("check_duplicate")
        return {"duplicate_found": True, "category": "flaky", "probability": 0.9, "short_cause": "Known issue", "suggestion": "Retry"}

    async def track_classify(state):
        call_order.append("classify_failure")
        return {"category": "should_not_reach"}

    async def track_recommend(state):
        call_order.append("build_recommendation")
        return {}

    workflow = build_analysis_workflow(
        compute_embedding_fn=track_compute,
        check_duplicate_fn=track_check,
        classify_failure_fn=track_classify,
        build_recommendation_fn=track_recommend,
    )

    initial_state: AnalysisState = {
        "error_text": "test error",
        "stack_trace": "",
        "embedding": [],
        "duplicate_found": False,
        "duplicate_analysis_id": None,
        "category": "",
        "probability": 0.0,
        "short_cause": "",
        "suggestion": "",
        "llm_model": "",
        "prompt_hash": "",
    }

    result = await workflow.ainvoke(initial_state)

    assert "compute_embedding" in call_order
    assert "check_duplicate" in call_order
    assert "classify_failure" not in call_order
    assert result.get("duplicate_found") is True