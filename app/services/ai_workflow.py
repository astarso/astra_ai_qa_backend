from typing import TypedDict


class AnalysisState(TypedDict):
    error_text: str
    stack_trace: str
    embedding: list[float]
    duplicate_found: bool
    duplicate_analysis_id: str | None
    category: str
    probability: float
    short_cause: str
    suggestion: str
    llm_model: str
    prompt_hash: str


def build_analysis_workflow(
    compute_embedding_fn,
    check_duplicate_fn,
    classify_failure_fn,
    build_recommendation_fn,
):
    from typing import Literal
    from langgraph.graph import StateGraph, START, END

    def route_duplicate(state: AnalysisState) -> Literal["duplicate", "classify"]:
        if state.get("duplicate_found"):
            return "duplicate"
        return "classify"

    graph = StateGraph(AnalysisState)
    graph.add_node("compute_embedding", compute_embedding_fn)
    graph.add_node("check_duplicate", check_duplicate_fn)
    graph.add_node("classify_failure", classify_failure_fn)
    graph.add_node("build_recommendation", build_recommendation_fn)

    graph.add_edge(START, "compute_embedding")
    graph.add_edge("compute_embedding", "check_duplicate")
    graph.add_conditional_edges(
        "check_duplicate",
        route_duplicate,
        {
            "duplicate": END,
            "classify": "classify_failure",
        },
    )
    graph.add_edge("classify_failure", "build_recommendation")
    graph.add_edge("build_recommendation", END)

    return graph.compile()