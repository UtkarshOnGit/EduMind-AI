import json
import logging
from typing import AsyncGenerator
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.schemas.chat import ChatQueryRequest
from app.workflows.graph import stream_rag_tokens_and_citations, execute_rag_pipeline

logger = logging.getLogger("ai_service.chat")
router = APIRouter()

async def sse_event_stream(payload: ChatQueryRequest) -> AsyncGenerator[str, None]:
    """
    Asynchronous Server-Sent Events (SSE) generator yielding tokens and citations.
    """
    logger.info(f"Initiating LangGraph SSE stream for course {payload.course_id}, query: '{payload.query}'")
    
    # Convert history items to dict
    history_dicts = [h.model_dump() for h in (payload.history or [])]

    try:
        for event in stream_rag_tokens_and_citations(
            query=payload.query,
            course_id=payload.course_id,
            student_id=payload.student_id,
            conversation_id=payload.conversation_id or "",
            history=history_dicts
        ):
            yield f"data: {json.dumps(event)}\n\n"
    except Exception as e:
        logger.error(f"Error in SSE stream generation: {e}")
        err_event = json.dumps({"error": str(e), "token": "\n[An error occurred while generating the response.]"})
        yield f"data: {err_event}\n\n"

    yield "data: [DONE]\n\n"

@router.post("/query")
async def chat_query(payload: ChatQueryRequest):
    """
    Course-specific RAG Chatbot query endpoint with Server-Sent Events (SSE) streaming.
    Streams token-by-token progressively and concludes with clickable video timestamp citations.
    """
    logger.info(f"Received streaming query for course {payload.course_id} from student {payload.student_id}")

    return StreamingResponse(
        sse_event_stream(payload),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
            "X-Accel-Buffering": "no"
        }
    )

@router.post("/query-sync")
async def chat_query_sync(payload: ChatQueryRequest):
    """
    Synchronous LangGraph RAG query execution (useful for integration tests and non-streaming clients).
    """
    logger.info(f"Received sync query for course {payload.course_id}")
    history_dicts = [h.model_dump() for h in (payload.history or [])]

    result = execute_rag_pipeline(
        query=payload.query,
        course_id=payload.course_id,
        student_id=payload.student_id,
        conversation_id=payload.conversation_id or "",
        history=history_dicts
    )

    return {
        "query": payload.query,
        "course_id": payload.course_id,
        "conversation_id": payload.conversation_id,
        "is_safe": result.get("is_safe", True),
        "answer": result.get("final_answer", ""),
        "citations": result.get("citations", []),
        "rephrased_query": result.get("rephrased_query", ""),
        "subqueries": result.get("subqueries", [])
    }
