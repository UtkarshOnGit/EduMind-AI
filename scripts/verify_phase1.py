import sys
import os
import subprocess
import httpx
import threading
import time

def check_mark(status):
    return "✅ PASS" if status else "❌ FAIL"

def run_checks():
    print("=" * 60)
    print("🎓 EduMind-AI Phase 1: Environment & Baseline Verification")
    print("=" * 60)
    all_passed = True

    # 1. Check Python version & venv
    py_ver = sys.version.split()[0]
    print(f"[1] Python Runtime: {py_ver}")
    is_py311 = sys.version_info.major == 3 and sys.version_info.minor == 11
    print(f"    Target: Python 3.11+ -> {check_mark(is_py311)}")
    if not is_py311:
        all_passed = False

    # 2. Check Python packages
    try:
        import fastapi
        import uvicorn
        import groq
        import qdrant_client
        import pymongo
        import langgraph
        print(f"[2] AI Microservice Dependencies (FastAPI, Groq, Qdrant, Pymongo, LangGraph) -> {check_mark(True)}")
    except ImportError as e:
        print(f"[2] Missing AI Microservice Dependency: {e} -> {check_mark(False)}")
        all_passed = False

    # 3. Check Qdrant In-Memory / Embedded Engine
    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(location=":memory:")
        print(f"[3] Qdrant Client (In-memory/Embedded Engine) -> {check_mark(True)}")
    except Exception as e:
        print(f"[3] Qdrant Engine Failed: {e} -> {check_mark(False)}")
        all_passed = False

    # Ensure ai-service is on Python path
    ai_service_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ai-service"))
    if ai_service_path not in sys.path:
        sys.path.insert(0, ai_service_path)

    # 4. Check FastAPI Health Endpoint
    try:
        from app.main import app
        from fastapi.testclient import TestClient
        test_client = TestClient(app)
        res = test_client.get("/api/v1/health")
        if res.status_code == 200 and res.json().get("status") == "ok":
            print(f"[4] FastAPI Service Health Endpoint (/api/v1/health) -> {check_mark(True)}")
        else:
            print(f"[4] FastAPI Service Health Endpoint returned {res.status_code} -> {check_mark(False)}")
            all_passed = False
    except Exception as e:
        print(f"[4] FastAPI Health Check Failed: {e} -> {check_mark(False)}")
        all_passed = False

    # 5. Check Node.js Backend & MongoDB via Node script
    try:
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
        node_check = subprocess.run(
            ["node", "-e", """
                import mongoose from 'mongoose';
                import app from './src/app.js';
                const uri = process.env.MONGODB_URI || 'mongodb://localhost:27017/edumind-ai';
                mongoose.connect(uri, { serverSelectionTimeoutMS: 2000 })
                  .then(() => {
                    console.log('MONGO_OK');
                    process.exit(0);
                  })
                  .catch(err => {
                    console.error('MONGO_FAIL:', err.message);
                    process.exit(1);
                  });
            """],
            cwd=backend_dir,
            capture_output=True,
            text=True,
            timeout=10
        )
        if node_check.returncode == 0:
            print(f"[5] Node.js Express App & MongoDB Connectivity -> {check_mark(True)}")
        else:
            print(f"[5] Node.js Express App & MongoDB Connectivity -> {check_mark(False)}")
            print("    Error:", node_check.stderr.strip() or node_check.stdout.strip())
            all_passed = False
    except Exception as e:
        print(f"[5] Node.js / MongoDB Verification Exception: {e} -> {check_mark(False)}")
        all_passed = False

    # 6. Check Frontend Build
    frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist", "index.html")
    if os.path.exists(frontend_dist):
        print(f"[6] React Frontend Production Build Artifacts -> {check_mark(True)}")
    else:
        print(f"[6] React Frontend Production Build Artifacts -> {check_mark(False)}")
        all_passed = False

    print("=" * 60)
    if all_passed:
        print("🎉 ALL PHASE 1 BASELINE CHECKS PASSED SUCCESSFULLY!")
    else:
        print("⚠️ SOME CHECKS FAILED. Please review the output above.")
    print("=" * 60)
    sys.exit(0 if all_passed else 1)

if __name__ == "__main__":
    run_checks()
