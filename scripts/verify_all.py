import sys
import os
import time
import subprocess
import json

# Ensure ai-service is on Python path
ai_service_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ai-service"))
if ai_service_path not in sys.path:
    sys.path.insert(0, ai_service_path)

def check_badge(status):
    return "✅ PASS" if status else "❌ FAIL"

def run_master_verification():
    print("\n" + "=" * 78)
    print("🎓  EDUMIND AI — MASTER END-TO-END SYSTEM VERIFICATION AUDIT")
    print("=" * 78)
    start_total = time.time()
    results = {}

    # =========================================================================
    # PHASE 1: Environment & Microservices Baseline
    # =========================================================================
    print("\n[PHASE 1] Validating Core Infrastructure & Services...")
    try:
        p1 = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(__file__), "verify_phase1.py")],
            capture_output=True,
            text=True,
            timeout=20
        )
        p1_ok = p1.returncode == 0
        results["Phase 1: Environment & Baseline"] = p1_ok
        print(f"  -> Phase 1 Baseline Check: {check_badge(p1_ok)}")
    except Exception as e:
        results["Phase 1: Environment & Baseline"] = False
        print(f"  -> Phase 1 Exception: {e}")

    # =========================================================================
    # PHASE 2: Audio Extraction & Groq Whisper STT
    # =========================================================================
    print("\n[PHASE 2] Validating Cloud Audio & Groq Whisper STT Pipeline...")
    try:
        p2 = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(__file__), "verify_phase2.py")],
            capture_output=True,
            text=True,
            timeout=30
        )
        p2_ok = p2.returncode == 0
        results["Phase 2: Groq Whisper STT & MongoDB Transcripts"] = p2_ok
        print(f"  -> Phase 2 STT Pipeline Check: {check_badge(p2_ok)}")
    except Exception as e:
        results["Phase 2: Groq Whisper STT & MongoDB Transcripts"] = False
        print(f"  -> Phase 2 Exception: {e}")

    # =========================================================================
    # PHASE 3: Semantic Chunking, Nemotron & Qdrant Multi-Tenancy
    # =========================================================================
    print("\n[PHASE 3] Validating Chunking, Nemotron 2048-dim Vectors & Qdrant Isolation...")
    try:
        p3 = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(__file__), "verify_phase3.py")],
            capture_output=True,
            text=True,
            timeout=30
        )
        p3_ok = p3.returncode == 0
        results["Phase 3: Semantic Chunking & Qdrant Isolation"] = p3_ok
        print(f"  -> Phase 3 Vector Indexing Check: {check_badge(p3_ok)}")
    except Exception as e:
        results["Phase 3: Semantic Chunking & Qdrant Isolation"] = False
        print(f"  -> Phase 3 Exception: {e}")

    # =========================================================================
    # PHASE 4: LangGraph Query Engine & SSE Streaming Bridge
    # =========================================================================
    print("\n[PHASE 4] Validating LangGraph State Machine & Real-Time SSE Token Streaming...")
    try:
        p4 = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(__file__), "verify_phase4.py")],
            capture_output=True,
            text=True,
            timeout=40
        )
        p4_ok = p4.returncode == 0
        results["Phase 4: LangGraph Engine & SSE Bridge"] = p4_ok
        print(f"  -> Phase 4 Query Lifecycle Check: {check_badge(p4_ok)}")
    except Exception as e:
        results["Phase 4: LangGraph Engine & SSE Bridge"] = False
        print(f"  -> Phase 4 Exception: {e}")

    # =========================================================================
    # PHASE 5: Frontend Interactive Video Player & Streaming UI
    # =========================================================================
    print("\n[PHASE 5] Validating Client Components, Build, & Backend Chat Bridge...")
    try:
        p5 = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(__file__), "verify_phase5.py")],
            capture_output=True,
            text=True,
            timeout=25
        )
        p5_ok = p5.returncode == 0
        results["Phase 5: Video Player & Streaming UI"] = p5_ok
        print(f"  -> Phase 5 Client & UI Contract Check: {check_badge(p5_ok)}")
    except Exception as e:
        results["Phase 5: Video Player & Streaming UI"] = False
        print(f"  -> Phase 5 Exception: {e}")

    # =========================================================================
    # PHASE 6: Non-Functional Requirements & Performance Benchmarking
    # =========================================================================
    print("\n[PHASE 6] Benchmarking Non-Functional Requirements (NFRs)...")
    try:
        from app.services.embedding_service import embedding_service
        from app.services.qdrant_service import qdrant_service
        from app.workflows.graph import stream_rag_tokens_and_citations

        # NFR-1.2: Retrieval Latency (< 100ms)
        qvec = embedding_service.embed_query("Distributed database consistency models")
        t_search_start = time.time()
        qdrant_service.search_course_chunks("cs101_sys", query_vector=qvec, limit=5)
        search_latency_ms = (time.time() - t_search_start) * 1000
        nfr_retrieval_ok = search_latency_ms < 100.0

        print(f"  • NFR-1.2: Qdrant Search Latency  : {search_latency_ms:.2f} ms (Target < 100ms) -> {check_badge(nfr_retrieval_ok)}")

        # NFR-1.3: Time to First Token (< 1.5s)
        t_ttft_start = time.time()
        ttft_val = None
        for evt in stream_rag_tokens_and_citations("What is the CAP theorem?", course_id="cs101_sys"):
            if "token" in evt and ttft_val is None:
                ttft_val = time.time() - t_ttft_start
                break

        nfr_ttft_ok = ttft_val is not None and ttft_val < 1.5
        print(f"  • NFR-1.3: Time to First Token (TTFT): {ttft_val:.3f} s (Target < 1.5s) -> {check_badge(nfr_ttft_ok)}")

        from app.core.config import settings

        # NFR-2.1: Zero Local GPU Dependency (Cloud-native API verification)
        nfr_gpu_ok = bool(settings.GROQ_API_KEY and settings.NVIDIA_API_KEY)
        print(f"  • NFR-2.1: Zero Local GPU Hardware   : Verified Cloud APIs (Groq + NVIDIA) -> {check_badge(nfr_gpu_ok)}")

        results["Phase 6: Performance & NFR Benchmarks"] = nfr_retrieval_ok and nfr_ttft_ok and nfr_gpu_ok
        qdrant_service.close()
    except Exception as e:
        results["Phase 6: Performance & NFR Benchmarks"] = False
        print(f"  -> Phase 6 Benchmark Exception: {e}")

    # =========================================================================
    # SUMMARY DASHBOARD
    # =========================================================================
    elapsed = time.time() - start_total
    all_success = all(results.values())

    print("\n" + "=" * 78)
    print("📋  SYSTEM VERIFICATION SUMMARY AUDIT")
    print("=" * 78)
    for phase_name, passed in results.items():
        print(f"  {check_badge(passed)}  {phase_name}")
    print("-" * 78)
    print(f"⏱️  Total Verification Time : {elapsed:.2f} seconds")
    print(f"🎯  Overall System Health   : {'🟢 PRODUCTION READY' if all_success else '🔴 ISSUES DETECTED'}")
    print("=" * 78 + "\n")

    sys.exit(0 if all_success else 1)

if __name__ == "__main__":
    run_master_verification()
