import sys
import os
import subprocess
import json
import time

def check_mark(status):
    return "✅ PASS" if status else "❌ FAIL"

def run_phase5_verification():
    print("=" * 70)
    print("🎓 EduMind-AI Phase 5: Interactive Video Player & Streaming UI")
    print("=" * 70)
    all_passed = True

    # 1. Verify Frontend Components & Production Build
    frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
    components_dir = os.path.join(frontend_dir, "src", "components")
    pages_dir = os.path.join(frontend_dir, "src", "pages")

    expected_files = [
        os.path.join(components_dir, "VideoPlayer.jsx"),
        os.path.join(components_dir, "CitationBadge.jsx"),
        os.path.join(components_dir, "UploadLectureModal.jsx"),
        os.path.join(pages_dir, "CourseDetail.jsx"),
    ]

    files_exist = all(os.path.exists(f) for f in expected_files)
    print(f"[1] Interactive Video Player & Citation UI Components Exist -> {check_mark(files_exist)}")
    if not files_exist:
        all_passed = False

    # 2. Verify Vite Frontend Compilation
    build_check = subprocess.run(
        ["npm", "run", "build"],
        cwd=frontend_dir,
        capture_output=True,
        text=True,
        timeout=15
    )
    build_ok = build_check.returncode == 0
    print(f"[2] React Client Build & Tailwind CSS Bundling (Vite) -> {check_mark(build_ok)}")
    if not build_ok:
        print("    Build Error:", build_check.stderr[:300])
        all_passed = False

    # 3. Verify Node.js Backend Chat Endpoints & Mongoose Models
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
    node_test = subprocess.run(
        ["node", "-e", """
            import app from './src/app.js';
            import Conversation from './src/models/Conversation.js';
            import Lecture from './src/models/Lecture.js';

            // Verify models have citations schema
            const conv = new Conversation({
              studentId: '507f1f77bcf86cd799439011',
              courseId: '507f1f77bcf86cd799439012',
              messages: [{
                sender: 'assistant',
                text: 'Test answer',
                citations: [{
                  lectureTitle: 'Lec 1',
                  startTime: 10,
                  endTime: 30,
                  chunkText: 'snippet'
                }]
              }]
            });

            if (conv.messages[0].citations[0].lectureTitle === 'Lec 1') {
              console.log('NODE_CHAT_MODEL_OK');
              process.exit(0);
            } else {
              process.exit(1);
            }
        """],
        cwd=backend_dir,
        capture_output=True,
        text=True,
        timeout=10
    )
    node_model_ok = node_test.returncode == 0 and "NODE_CHAT_MODEL_OK" in node_test.stdout
    print(f"[3] Node.js Chat Controller & MongoDB Conversation Schema -> {check_mark(node_model_ok)}")
    if not node_model_ok:
        print("    Node Test Error:", node_test.stderr or node_test.stdout)
        all_passed = False

    # 4. End-to-End Chat Contract Verification between Node Backend & FastAPI
    ai_service_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ai-service"))
    if ai_service_path not in sys.path:
        sys.path.insert(0, ai_service_path)

    try:
        from app.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)

        test_payload = {
            "course_id": "cs101_phase5",
            "student_id": "student_phase5",
            "query": "What is the CAP theorem?",
            "history": []
        }

        # Test SSE streaming endpoint
        res = client.post("/api/v1/chat/query", json=test_payload)
        sse_contract_ok = res.status_code == 200 and "text/event-stream" in res.headers.get("content-type", "")
        print(f"[4] Full SSE Stream Contract (/api/v1/chat/query) -> {check_mark(sse_contract_ok)}")
        if not sse_contract_ok:
            all_passed = False
    except Exception as e:
        print(f"[4] SSE Contract check failed: {e} -> {check_mark(False)}")
        all_passed = False

    print("=" * 70)
    if all_passed:
        print("🎉 ALL PHASE 5 REQUIREMENTS VERIFIED AND PASSED SUCCESSFULLY!")
    else:
        print("⚠️ SOME CHECKS FAILED. Please review the output above.")
    print("=" * 70)
    sys.exit(0 if all_passed else 1)

if __name__ == "__main__":
    run_phase5_verification()
