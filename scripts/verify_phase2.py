import sys
import os
import wave
import math
import struct
import tempfile
from bson import ObjectId

# Ensure ai-service is on Python path
ai_service_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ai-service"))
if ai_service_path not in sys.path:
    sys.path.insert(0, ai_service_path)

def check_mark(status):
    return "✅ PASS" if status else "❌ FAIL"

def generate_test_audio() -> str:
    """Generate a clean 1.5-second test WAV file with a tone."""
    fd, path = tempfile.mkstemp(suffix=".wav", prefix="edumind_test_tone_")
    os.close(fd)
    with wave.open(path, 'w') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        # 1.5 seconds of 440Hz tone
        total_samples = int(16000 * 1.5)
        for i in range(total_samples):
            val = int(32767.0 * 0.1 * math.sin(2.0 * math.pi * 440.0 * i / 16000))
            wav.writeframes(struct.pack('<h', val))
    return path

def run_phase2_verification():
    print("=" * 65)
    print("🎓 EduMind-AI Phase 2: Audio Extraction & Groq Whisper STT")
    print("=" * 65)
    all_passed = True

    # 1. MediaService Audio Transformation Check
    try:
        from app.services.media_service import media_service
        sample_video_url = "https://res.cloudinary.com/university/video/upload/v1700000000/courses/cs101/lecture_1.mp4"
        audio_url = media_service.get_audio_transformation_url(sample_video_url)
        expected_audio_url = "https://res.cloudinary.com/university/video/upload/f_mp3/v1700000000/courses/cs101/lecture_1.mp3"
        url_match = audio_url == expected_audio_url
        print(f"[1] Cloudinary Video -> Audio URL Transformation -> {check_mark(url_match)}")
        if not url_match:
            print(f"    Expected: {expected_audio_url}")
            print(f"    Got:      {audio_url}")
            all_passed = False
    except Exception as e:
        print(f"[1] MediaService URL transformation failed: {e} -> {check_mark(False)}")
        all_passed = False

    # 2. Groq Whisper API Live Transcription Check
    temp_audio = None
    try:
        from app.services.transcription_service import transcription_service
        temp_audio = generate_test_audio()
        result = transcription_service.transcribe_file(temp_audio, model="whisper-large-v3-turbo")
        
        has_blocks = len(result.get("blocks", [])) > 0
        has_duration = result.get("duration", 0.0) > 0.0
        first_block = result.get("blocks", [{}])[0]
        has_timestamps = "start_time" in first_block and "end_time" in first_block

        groq_ok = has_blocks and has_duration and has_timestamps
        print(f"[2] Groq Whisper API (whisper-large-v3-turbo) Zero-GPU STT -> {check_mark(groq_ok)}")
        print(f"    Model: whisper-large-v3-turbo | Duration: {result.get('duration')}s | Language: {result.get('language')}")
        if not groq_ok:
            all_passed = False
    except Exception as e:
        print(f"[2] Groq Whisper API Transcription failed: {e} -> {check_mark(False)}")
        all_passed = False
    finally:
        if temp_audio and os.path.exists(temp_audio):
            try:
                os.remove(temp_audio)
            except Exception:
                pass

    # 3. Fault-Tolerant MongoDB Transcript Storage Check
    test_course_id = str(ObjectId())
    test_lecture_id = str(ObjectId())
    try:
        from app.services.db_service import db_service
        test_blocks = [
            {"block_index": 0, "start_time": 0.0, "end_time": 4.5, "text": "Welcome to Computer Architecture."},
            {"block_index": 1, "start_time": 4.5, "end_time": 10.2, "text": "Today we will analyze pipelining hazard resolution."}
        ]

        # Save blocks
        saved_count = db_service.save_transcript_blocks(test_course_id, test_lecture_id, test_blocks)
        saved_ok = saved_count == 2

        # Retrieve blocks
        retrieved_blocks = db_service.get_transcript_blocks(test_lecture_id)
        retrieve_ok = (
            len(retrieved_blocks) == 2 and 
            retrieved_blocks[0]["text"] == "Welcome to Computer Architecture." and
            retrieved_blocks[1]["startTime"] == 4.5
        )

        db_ok = saved_ok and retrieve_ok
        print(f"[3] Fault-Tolerant MongoDB Transcript Storage & Retrieval -> {check_mark(db_ok)}")
        if not db_ok:
            all_passed = False

        # Cleanup test blocks
        db_service.db.transcriptblocks.delete_many({"lectureId": ObjectId(test_lecture_id)})
    except Exception as e:
        print(f"[3] MongoDB Transcript persistence failed: {e} -> {check_mark(False)}")
        all_passed = False

    # 4. FastAPI Ingest Endpoint Contract Check (202 Accepted)
    try:
        from app.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        ingest_payload = {
            "lecture_id": str(ObjectId()),
            "course_id": str(ObjectId()),
            "title": "Introduction to AI",
            "cloudinary_url": "https://res.cloudinary.com/test/video/upload/v1/test.mp4"
        }
        res = client.post("/api/v1/ingest/lecture", json=ingest_payload)
        ingest_endpoint_ok = res.status_code == 202 and res.json().get("status") == "processing"
        print(f"[4] FastAPI Background Ingestion Dispatch Endpoint (202 Accepted) -> {check_mark(ingest_endpoint_ok)}")
        if not ingest_endpoint_ok:
            print("    Response:", res.status_code, res.text)
            all_passed = False
    except Exception as e:
        print(f"[4] FastAPI Ingest Endpoint check failed: {e} -> {check_mark(False)}")
        all_passed = False

    print("=" * 65)
    if all_passed:
        print("🎉 ALL PHASE 2 REQUIREMENTS VERIFIED AND PASSED SUCCESSFULLY!")
    else:
        print("⚠️ SOME CHECKS FAILED. Please review the output above.")
    print("=" * 65)
    sys.exit(0 if all_passed else 1)

if __name__ == "__main__":
    run_phase2_verification()
