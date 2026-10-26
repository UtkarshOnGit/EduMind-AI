from typing import TypedDict, List, Dict, Any, Optional

class ChatState(TypedDict):
    """
    LangGraph Workflow State representing the query lifecycle through modular nodes.
    """
    # Inputs
    query: str
    course_id: str
    student_id: Optional[str]
    conversation_id: Optional[str]
    history: List[Dict[str, str]]

    # 1. Guardrail evaluation
    is_safe: bool
    guardrail_message: Optional[str]

    # 2. Rephraser (short-term memory & context resolution)
    rephrased_query: str

    # 3. Subquery splitter (multi-topic / comparative query decomposition)
    subqueries: List[str]

    # 4. Relevant chunk retrieval
    retrieved_chunks: List[Dict[str, Any]]

    # 5. Similarity threshold filtering & reranker
    filtered_chunks: List[Dict[str, Any]]

    # 6. Citations and Grounded answer
    citations: List[Dict[str, Any]]
    final_answer: str
