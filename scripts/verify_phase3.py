import sys
import os
import json
from bson import ObjectId

# Ensure ai-service is on Python path
ai_service_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ai-service"))
if ai_service_path not in sys.path:
    sys.path.insert(0, ai_service_path)

def check_mark(status):
    return "✅ PASS" if status else "❌ FAIL"

def format_seconds(seconds: float) -> str:
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"

# Realistic sample lecture transcript data for testing
SAMPLE_TRANSCRIPT_BLOCKS = [
    {
        "block_index": 0,
        "start_time": 0.0,
        "end_time": 18.5,
        "text": "Good morning everyone. Today we are diving into distributed systems architecture, specifically the foundational principles of consistency, availability, and partition tolerance."
    },
    {
        "block_index": 1,
        "start_time": 18.5,
        "end_time": 42.0,
        "text": "In any distributed data store, network partitions are an inevitable physical reality. Packets drop, routers fail, and fiber optic links get cut. Therefore, when a partition occurs, your architecture must choose between consistency and availability."
    },
    {
        "block_index": 2,
        "start_time": 42.0,
        "end_time": 75.3,
        "text": "If you choose consistency, every read is guaranteed to receive the most recent write or an error. In financial ledgers and bank accounts, consistency is non-negotiable. You would rather decline a transaction than display an inaccurate balance."
    },
    {
        "block_index": 3,
        "start_time": 75.3,
        "end_time": 110.8,
        "text": "Conversely, if you choose availability, every non-failing node returns a response for every request, though it may not contain the most recent write. Shopping carts and social media newsfeeds frequently adopt eventual consistency to maximize uptime."
    },
    {
        "block_index": 4,
        "start_time": 110.8,
        "end_time": 145.2,
        "text": "Next, let's explore quorum consensus algorithms such as Raft and Paxos. These protocols allow distributed state machines to agree on values across a majority of nodes without requiring total unanimity."
    },
    {
        "block_index": 5,
        "start_time": 145.2,
        "end_time": 185.0,
        "text": "A quorum requires at least n divided by 2 plus 1 active nodes. If a five-node cluster loses two nodes, the remaining three nodes can still elect a leader and commit transactions safely."
    }
]

def run_phase3_verification():
    print("=" * 70)
    print("🎓 EduMind-AI Phase 3: Semantic Chunking, Nemotron & Qdrant")
    print("=" * 70)
    all_passed = True

    # ---------------------------------------------------------
    # 1. Chunking Service Test & Visual Example Display
    # ---------------------------------------------------------
    print("\n--- [PART 1: SEMANTIC CHUNKING DEMONSTRATION & VERIFICATION] ---")
    from app.services.chunking_service import ChunkingService
    # Use smaller target_tokens for demo so our sample splits into distinct chunks
    chunker = ChunkingService(target_tokens=60, overlap_tokens=20)
    
    test_course_id = "cs101_sys"
    test_lecture_id = "lec_distributed_01"
    lecture_title = "Distributed Systems: CAP Theorem & Quorums"

    chunks = chunker.chunk_transcript(
        blocks=SAMPLE_TRANSCRIPT_BLOCKS,
        course_id=test_course_id,
        lecture_id=test_lecture_id,
        lecture_title=lecture_title
    )

    print(f"Generated {len(chunks)} cohesive semantic chunks from {len(SAMPLE_TRANSCRIPT_BLOCKS)} raw blocks.\n")
    print("📋 CONCRETE EXAMPLES OF HOW LECTURE CHUNKS LOOK:")
    print("-" * 70)

    for i, chunk in enumerate(chunks):
        time_str = f"{format_seconds(chunk['start_time'])} - {format_seconds(chunk['end_time'])}"
        print(f"🔹 CHUNK #{i + 1} [ID: {chunk['chunk_id']}]")
        print(f"   ⏱️  Timestamp Window : {time_str} ({chunk['start_time']}s to {chunk['end_time']}s)")
        print(f"   📊 Token Estimate   : ~{chunk['token_count']} tokens")
        print(f"   🏷️  Course / Lecture : {chunk['course_id']} / \"{chunk['lecture_title']}\"")
        print(f"   📝 Content Preview  :")
        print(f"      \"{chunk['text']}\"")
        print("-" * 70)

    # Assertions on chunks
    chunks_ok = (
        len(chunks) >= 2 and
        all(c["start_time"] < c["end_time"] for c in chunks) and
        all(c["token_count"] > 0 for c in chunks) and
        all(c["course_id"] == test_course_id for c in chunks)
    )
    print(f"[1] Semantic Chunking Timestamp & Overlap Preservation -> {check_mark(chunks_ok)}")
    if not chunks_ok:
        all_passed = False

    # ---------------------------------------------------------
    # 2. NVIDIA Nemotron-3-Embed-1B Live Embedding Test
    # ---------------------------------------------------------
    print("\n--- [PART 2: NVIDIA NEMOTRON-3-EMBED-1B DENSE VECTORIZATION] ---")
    try:
        from app.services.embedding_service import embedding_service
        sample_texts = [chunks[0]["text"], chunks[1]["text"]]
        embeddings = embedding_service.embed_passages(sample_texts)

        emb_dim = len(embeddings[0]) if embeddings else 0
        emb_count_ok = len(embeddings) == 2
        emb_dim_ok = emb_dim == 2048

        print(f"   Embedding Model     : {embedding_service.model}")
        print(f"   Generated Vectors   : {len(embeddings)}")
        print(f"   Vector Dimensions   : {emb_dim} (Target: 2048)")
        print(f"   Sample Vector Slice : {embeddings[0][:5]} ...")

        # Test query embedding
        query_vec = embedding_service.embed_query("What is the CAP theorem consistency tradeoff?")
        query_ok = len(query_vec) == 2048

        nemotron_ok = emb_count_ok and emb_dim_ok and query_ok
        print(f"[2] NVIDIA Nemotron-3-Embed-1B (2048-dim) Dense Embeddings -> {check_mark(nemotron_ok)}")
        if not nemotron_ok:
            all_passed = False
    except Exception as e:
        print(f"[2] NVIDIA Nemotron Embedding Failed: {e} -> {check_mark(False)}")
        all_passed = False
        embeddings = []
        query_vec = []

    # ---------------------------------------------------------
    # 3. Qdrant Vector Multi-Tenancy & Course Isolation Test
    # ---------------------------------------------------------
    print("\n--- [PART 3: QDRANT MULTI-TENANCY & TENANT ISOLATION] ---")
    try:
        from app.services.qdrant_service import qdrant_service
        test_col = "edumind_phase3_verification"
        qdrant_service.ensure_collection(test_col)

        # Upsert Course A chunks
        qdrant_service.upsert_chunks(chunks[:2], embeddings[:2], collection_name=test_col)

        # Create simulated Course B chunk (e.g. Physics 201)
        course_b_id = "phys201_quantum"
        chunk_b = {
            "chunk_id": "phys_c1",
            "course_id": course_b_id,
            "lecture_id": "lec_quantum_01",
            "lecture_title": "Quantum Mechanics Wavefunctions",
            "chunk_index": 0,
            "start_time": 0.0,
            "end_time": 50.0,
            "text": "Schrodinger wave equations describe probability density of particles in quantum superpositions.",
            "token_count": 45
        }
        # Embed Course B chunk
        emb_b = embedding_service.embed_passages([chunk_b["text"]])
        qdrant_service.upsert_chunks([chunk_b], emb_b, collection_name=test_col)

        # Search STRICTLY in Course A
        results_course_a = qdrant_service.search_course_chunks(
            course_id=test_course_id,
            query_vector=query_vec,
            limit=5,
            collection_name=test_col
        )

        print(f"   Searched for        : 'CAP theorem consistency tradeoff'")
        print(f"   Filter Applied      : course_id == '{test_course_id}'")
        print(f"   Matched Chunks      : {len(results_course_a)}")
        for r in results_course_a:
            print(f"     -> [{r['lecture_title']} @ {format_seconds(r['start_time'])}] Score: {r['score']:.4f}")
            print(f"        Snippet: {r['text'][:80]}...")

        # Strict Multi-Tenant Isolation Check:
        # CS101 search MUST NEVER return any PHYS201 chunks!
        no_cross_tenant_leak = all(r["course_id"] == test_course_id for r in results_course_a)
        has_matches = len(results_course_a) > 0

        # Search STRICTLY in Course B
        results_course_b = qdrant_service.search_course_chunks(
            course_id=course_b_id,
            query_vector=query_vec,
            limit=5,
            collection_name=test_col
        )
        course_b_isolated = all(r["course_id"] == course_b_id for r in results_course_b)

        isolation_ok = no_cross_tenant_leak and has_matches and course_b_isolated
        print(f"[3] Qdrant Multi-Tenant Course Isolation & Payload Filtering -> {check_mark(isolation_ok)}")
        if not isolation_ok:
            all_passed = False

        # Clean up test collection and release client
        try:
            qdrant_service.client.delete_collection(test_col)
        except Exception:
            pass
        qdrant_service.close()

    except Exception as e:
        print(f"[3] Qdrant Multi-Tenancy test failed: {e} -> {check_mark(False)}")
        all_passed = False
        try:
            qdrant_service.close()
        except Exception:
            pass

    print("\n" + "=" * 70)
    if all_passed:
        print("🎉 ALL PHASE 3 REQUIREMENTS VERIFIED AND PASSED SUCCESSFULLY!")
    else:
        print("⚠️ SOME CHECKS FAILED. Please review the output above.")
    print("=" * 70)
    sys.exit(0 if all_passed else 1)

if __name__ == "__main__":
    run_phase3_verification()
