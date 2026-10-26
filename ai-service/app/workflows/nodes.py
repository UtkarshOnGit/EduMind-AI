import logging
import re
from typing import Dict, Any, List
from app.workflows.state import ChatState
from app.core.config import settings
from app.services.llm_service import llm_service
from app.services.embedding_service import embedding_service
from app.services.qdrant_service import qdrant_service

logger = logging.getLogger("ai_service.workflows.nodes")

# Prompt injection & security guardrail patterns
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior)\s+instructions",
    r"disregard\s+(all\s+)?guidelines",
    r"system\s+prompt",
    r"jailbreak",
    r"dan\s+mode",
    r"you\s+are\s+now\s+an\s+unrestricted",
    r"pretend\s+you\s+have\s+no\s+rules",
    r"bypass\s+filters"
]

def guardrail_node(state: ChatState) -> Dict[str, Any]:
    """
    Node 1: Evaluates query safety, academic scope, and prompt injection attempts.
    """
    query = state.get("query", "").strip()
    logger.info(f"[Guardrail Node] Evaluating query safety: '{query[:80]}...'")

    # Check against known adversarial injection patterns
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, query, re.IGNORECASE):
            logger.warning(f"[Guardrail Node] Prompt injection pattern detected: '{pattern}'")
            return {
                "is_safe": False,
                "guardrail_message": "I am your course-grounded AI assistant. Please ask academic questions related to this course's lecture materials."
            }

    # Extremely short query or spam check
    if len(query) < 2:
        return {
            "is_safe": False,
            "guardrail_message": "Please enter a valid course-related question."
        }

    return {
        "is_safe": True,
        "guardrail_message": None
    }

def rephraser_node(state: ChatState) -> Dict[str, Any]:
    """
    Node 2: Rephraser - uses short-term conversation memory (history) to rewrite
    ambiguous follow-ups, pronouns, and references into a standalone query.
    """
    query = state.get("query", "").strip()
    history = state.get("history", [])

    if not history:
        logger.info("[Rephraser Node] No prior history in this chat session. Using raw query.")
        return {"rephrased_query": query}

    logger.info(f"[Rephraser Node] Rephrasing with {len(history)} previous conversational turns...")

    # Build conversational history transcript
    history_transcript = ""
    for item in history[-6:]:  # Focus on the most recent 6 messages
        role = "Student" if item.get("sender") in ["student", "user"] else "Assistant"
        text = item.get("text", "").strip()
        # Truncate long assistant responses in memory transcript for speed
        if len(text) > 300:
            text = text[:300] + "..."
        history_transcript += f"{role}: {text}\n"

    prompt_messages = [
        {
            "role": "system",
            "content": (
                "You are an academic query rephraser for a course-grounded assistant. "
                "Given a conversation history between a student and an assistant, rewrite the student's latest question "
                "into a standalone, unambiguous search query that preserves the context and resolves all pronouns "
                "('it', 'this', 'that', 'those', 'the previous one', 'both of them').\n"
                "Rules:\n"
                "1. If the question is already clear and self-contained, return it unchanged.\n"
                "2. Do NOT answer the question.\n"
                "3. Return ONLY the rewritten question, without quotes or explanations."
            )
        },
        {
            "role": "user",
            "content": f"Chat History:\n{history_transcript}\nLatest Question: {query}\n\nStandalone Query:"
        }
    ]

    try:
        rephrased = llm_service.generate(prompt_messages, temperature=0.1).strip()
        rephrased = rephrased.strip('"\'')
        logger.info(f"[Rephraser Node] Successfully rephrased query to: '{rephrased}'")
        return {"rephrased_query": rephrased if rephrased else query}
    except Exception as e:
        logger.warning(f"[Rephraser Node] Rephrasing error: {e}. Falling back to original query.")
        return {"rephrased_query": query}

def subquery_splitter_node(state: ChatState) -> Dict[str, Any]:
    """
    Node 3: Subquery Splitter - decomposes compound, multi-part, or comparative
    questions into 1-3 distinct atomic subqueries for focused vector retrieval.
    """
    query = state.get("rephrased_query") or state.get("query", "").strip()

    # Fast heuristic check: if short and lacks conjunctions/comparison, keep as single query
    compound_signals = [" and ", " vs ", " versus ", " difference between ", " compare ", " as well as ", "?", ";"]
    has_compound_signal = any(sig in query.lower() for sig in compound_signals)
    word_count = len(query.split())

    if not has_compound_signal and word_count < 10:
        logger.info(f"[Subquery Splitter Node] Simple single query detected: '{query}'")
        return {"subqueries": [query]}

    logger.info(f"[Subquery Splitter Node] Analyzing query for subquery decomposition: '{query}'")

    prompt_messages = [
        {
            "role": "system",
            "content": (
                "You are an academic query decomposition engine for a vector search system. "
                "Analyze the user's query:\n"
                "- If the query asks multiple questions, compares concepts, or asks for multiple properties (e.g. 'what is X and how does it compare to Y?'), "
                "break it into 2 or 3 atomic search queries.\n"
                "- If it is a single focused question, output just that single question.\n"
                "Rules:\n"
                "1. Each subquery must be a complete standalone search query.\n"
                "2. Output format: numbered list with one query per line (e.g. '1. ...\\n2. ...').\n"
                "3. Do NOT provide answers or explanations."
            )
        },
        {
            "role": "user",
            "content": f"Query: {query}\n\nDecomposed Queries:"
        }
    ]

    try:
        response = llm_service.generate(prompt_messages, temperature=0.1).strip()
        lines = [line.strip() for line in response.split("\n") if line.strip()]
        subqueries = []
        for line in lines:
            cleaned = re.sub(r"^\d+[\.\)]\s*", "", line).strip().strip('"\'')
            if cleaned and len(cleaned) > 3:
                subqueries.append(cleaned)

        if not subqueries:
            subqueries = [query]

        # Cap at maximum 3 subqueries to avoid excessive retrieval latency
        subqueries = subqueries[:3]
        logger.info(f"[Subquery Splitter Node] Decomposed into {len(subqueries)} subqueries: {subqueries}")
        return {"subqueries": subqueries}
    except Exception as e:
        logger.warning(f"[Subquery Splitter Node] Splitter error: {e}. Falling back to rephrased query.")
        return {"subqueries": [query]}

def retrieval_node(state: ChatState) -> Dict[str, Any]:
    """
    Node 4: Relevant Chunk Retriever - embeds each subquery and retrieves top
    candidate chunks from Qdrant with course-level isolation.
    """
    course_id = state.get("course_id")
    subqueries = state.get("subqueries") or [state.get("rephrased_query") or state.get("query")]
    all_chunks = []
    seen_ids = set()

    for subq in subqueries:
        try:
            logger.info(f"[Retrieval Node] Embedding and retrieving for subquery: '{subq}' in course {course_id}")
            query_vector = embedding_service.embed_query(subq)

            # Strict multi-tenant isolation via course_id payload filter
            chunks = qdrant_service.search_course_chunks(
                course_id=course_id,
                query_vector=query_vector,
                limit=5
            )

            for chunk in chunks:
                cid = chunk.get("chunk_id")
                if cid and cid not in seen_ids:
                    seen_ids.add(cid)
                    all_chunks.append(chunk)
                elif not cid:
                    all_chunks.append(chunk)
        except Exception as e:
            logger.error(f"[Retrieval Node] Error retrieving for subquery '{subq}': {e}")

    logger.info(f"[Retrieval Node] Retrieved {len(all_chunks)} unique candidate chunks for course {course_id}")
    return {"retrieved_chunks": all_chunks}

def threshold_filter_node(state: ChatState) -> Dict[str, Any]:
    """
    Node 5: Similarity Threshold & Reranker - filters out non-relevant chunks
    to avoid hallucination and prepares structured citations.
    """
    chunks = state.get("retrieved_chunks", [])
    threshold = getattr(settings, "SIMILARITY_THRESHOLD", 0.20)

    # Filter chunks exceeding minimum cosine similarity
    filtered = [c for c in chunks if c.get("score", 0.0) >= threshold]
    filtered.sort(key=lambda x: x.get("score", 0.0), reverse=True)

    # Keep top 4 most relevant chunks
    accepted_chunks = filtered[:4]

    # Format structured citations
    citations = []
    for c in accepted_chunks:
        citations.append({
            "lecture_id": c.get("lecture_id", ""),
            "lecture_title": c.get("lecture_title") or "Course Lecture",
            "start_time": c.get("start_time", 0.0),
            "end_time": c.get("end_time", 0.0),
            "chunk_text": (c.get("text") or "")[:200] + "...",
            "score": c.get("score", 0.0)
        })

    logger.info(
        f"[Threshold Filter Node] {len(accepted_chunks)} of {len(chunks)} chunks met threshold ({threshold})"
    )
    return {
        "filtered_chunks": accepted_chunks,
        "citations": citations
    }

def generate_node(state: ChatState) -> Dict[str, Any]:
    """
    Node 6: Grounded Generator - strictly synthesizes response from filtered lecture chunks.
    """
    if not state.get("is_safe", True):
        return {
            "final_answer": state.get(
                "guardrail_message",
                "I am your course AI assistant. Please ask academic questions about this course."
            )
        }

    chunks = state.get("filtered_chunks", [])
    if not chunks:
        return {
            "final_answer": "This topic was not covered in the uploaded lecture materials for this course."
        }

    query = state.get("query", "")
    
    # Format context with lecture titles and timestamps
    context_text = ""
    for i, c in enumerate(chunks):
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

    try:
        answer = llm_service.generate(messages, temperature=0.35)
        return {"final_answer": answer}
    except Exception as e:
        logger.error(f"[Generate Node] Generation error: {e}")
        return {"final_answer": "An error occurred while generating the grounded answer."}
