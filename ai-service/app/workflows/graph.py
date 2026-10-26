import logging
from typing import Dict, Any, Generator, Optional
from langgraph.graph import StateGraph, END
from app.workflows.state import ChatState
from app.workflows.nodes import (
    guardrail_node,
    rephraser_node,
    subquery_splitter_node,
    retrieval_node,
    threshold_filter_node,
    generate_node
)
from app.services.llm_service import llm_service

logger = logging.getLogger("ai_service.workflows.graph")

def check_guardrail_condition(state: ChatState) -> str:
    """Conditional edge router: proceed to rephraser or deflect immediately to generate."""
    if not state.get("is_safe", True):
        logger.info("[Workflow Router] Guardrail triggered -> Deflecting directly to generate/END.")
        return "deflect"
    return "proceed"

def build_rag_graph():
    """
    Constructs and compiles the complete LangGraph StateGraph:
    guardrail -> (conditional)
      ├── proceed: rephraser -> subquery_splitter -> retrieval -> threshold_filter -> generate -> END
      └── deflect: generate -> END
    """
    workflow = StateGraph(ChatState)

    # Register modular nodes
    workflow.add_node("guardrail", guardrail_node)
    workflow.add_node("rephraser", rephraser_node)
    workflow.add_node("subquery_splitter", subquery_splitter_node)
    workflow.add_node("retrieval", retrieval_node)
    workflow.add_node("threshold_filter", threshold_filter_node)
    workflow.add_node("generate", generate_node)

    # Set entry point
    workflow.set_entry_point("guardrail")

    # Add conditional branching after guardrail
    workflow.add_conditional_edges(
        "guardrail",
        check_guardrail_condition,
        {
            "proceed": "rephraser",
            "deflect": "generate"
        }
    )

    # Pipeline sequence
    workflow.add_edge("rephraser", "subquery_splitter")
    workflow.add_edge("subquery_splitter", "retrieval")
    workflow.add_edge("retrieval", "threshold_filter")
    workflow.add_edge("threshold_filter", "generate")
    workflow.add_edge("generate", END)

    compiled = workflow.compile()
    logger.info("LangGraph course-grounded multi-node RAG workflow compiled successfully.")
    return compiled

# Singleton compiled graph
rag_graph = build_rag_graph()

def execute_rag_pipeline(
    query: str,
    course_id: str,
    student_id: str = "",
    conversation_id: str = "",
    history: list = None
) -> ChatState:
    """
    Executes the full LangGraph RAG workflow synchronously and returns final state.
    """
    initial_state: ChatState = {
        "query": query,
        "course_id": course_id,
        "student_id": student_id,
        "conversation_id": conversation_id,
        "history": history or [],
        "is_safe": True,
        "guardrail_message": None,
        "rephrased_query": "",
        "subqueries": [],
        "retrieved_chunks": [],
        "filtered_chunks": [],
        "citations": [],
        "final_answer": ""
    }

    result = rag_graph.invoke(initial_state)
    return result

def stream_rag_tokens_and_citations(
    query: str,
    course_id: str,
    student_id: str = "",
    conversation_id: str = "",
    history: list = None
) -> Generator[Dict[str, Any], None, None]:
    """
    Generator for Server-Sent Events (SSE):
    Executes the multi-node pipeline:
    guardrail -> rephraser -> subquery_splitter -> retrieval -> threshold_filter
    Streams grounded response tokens and yields structured citations metadata.
    """
    initial_state: ChatState = {
        "query": query,
        "course_id": course_id,
        "student_id": student_id,
        "conversation_id": conversation_id,
        "history": history or [],
        "is_safe": True,
        "guardrail_message": None,
        "rephrased_query": "",
        "subqueries": [],
        "retrieved_chunks": [],
        "filtered_chunks": [],
        "citations": [],
        "final_answer": ""
    }

    # Step 1: Guardrail Node
    s1 = guardrail_node(initial_state)
    initial_state.update(s1)

    if not initial_state["is_safe"]:
        deflect_msg = initial_state.get(
            "guardrail_message",
            "I am your course AI assistant. Please ask academic questions about this course."
        )
        for word in deflect_msg.split(" "):
            yield {"token": word + " "}
        yield {"citations": []}
        return

    # Step 2: Rephraser Node (Short-Term Memory & Pronoun Resolution)
    s2 = rephraser_node(initial_state)
    initial_state.update(s2)

    # Step 3: Subquery Splitter Node (Decomposition of multi-part questions)
    s3 = subquery_splitter_node(initial_state)
    initial_state.update(s3)

    # Step 4: Relevant Chunk Retrieval Node
    s4 = retrieval_node(initial_state)
    initial_state.update(s4)

    # Step 5: Similarity Threshold & Reranker Node
    s5 = threshold_filter_node(initial_state)
    initial_state.update(s5)

    filtered_chunks = initial_state.get("filtered_chunks", [])
    citations = initial_state.get("citations", [])

    # If no relevant chunks meet threshold, stream grounded deflection
    if not filtered_chunks:
        no_cov_msg = "This topic was not covered in the uploaded lecture materials for this course."
        for word in no_cov_msg.split(" "):
            yield {"token": word + " "}
        yield {"citations": []}
        return

    # Step 6: Stream grounded generation tokens
    context_text = ""
    for i, c in enumerate(filtered_chunks):
        title = c.get("lecture_title") or "Lecture"
        st = c.get("start_time", 0.0)
        et = c.get("end_time", 0.0)
        m_s = f"{int(st // 60):02d}:{int(st % 60):02d}"
        m_e = f"{int(et // 60):02d}:{int(et % 60):02d}"
        context_text += f"\n--- Excerpt {i+1} [{title} @ {m_s} - {m_e}] ---\n{c.get('text', '')}\n"

    system_prompt = (
        "You are Buddy, a friendly, encouraging, and highly intuitive AI professor for this course—speaking with the clear, conversational teaching voice of Google Gemini.\n\n"
        "Your Teaching Philosophy:\n"
        "1. Teach with Human Intuition: Speak in warm, conversational English like a teacher explaining on a whiteboard during office hours. Explain the core 'why' and provide intuitive mental models before diving into any code.\n"
        "2. Synthesize, Don't Parrot: Do not quote raw transcript fragments or repeatedly repeat 'as stated in the lecture'. Instead, weave the lecture's teachings into a cohesive, articulate lesson tailored directly to what the student is asking.\n"
        "3. Strict Grounding Truth: While explaining simply, every fact, algorithm, and concept must remain 100% faithful to the provided lecture excerpts. Never hallucinate facts not taught by the professor.\n"
        "4. Human Presentation (NO UNNECESSARY SYMBOLS OR EMOJIS):\n"
        "   - NEVER use LaTeX math display blocks ($$ ... $$ or \\[ \\]) or symbols like \\times, \\ge. Write math in plain, readable text (e.g., '2^k >= n', 'O(n)', 'O(log n)').\n"
        "   - NEVER use raw HTML tags (like <br>) or dense markdown tables. Use clean, natural paragraphs and clear bullet points instead.\n"
        "   - NEVER use emoji bullet headers (like 1️⃣, 2️⃣, 🧩, 🎓, 🚀). Keep the formatting natural, clean, and elegant.\n"
        "   - Use short, simple code snippets only to illustrate the loop or concept simply.\n"
        "5. Off-Topic Check: If the question cannot be answered from the lecture materials, warmly respond: 'This topic was not covered in the uploaded lecture materials for this course.'"
    )
    user_prompt = f"Lecture Excerpts:\n{context_text}\n\nStudent Question: {query}\n\nIntuitive Explanation:"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    for token in llm_service.stream_generate(messages, temperature=0.35):
        yield {"token": token}

    # Final event sends structured citation metadata
    yield {"citations": citations}
