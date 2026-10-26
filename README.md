# EduMind AI 🎓🤖

> **Course-Grounded AI Teaching Platform** with zero-GPU automated lecture transcription, high-precision semantic retrieval, and real-time streaming answers with clickable video timestamp citations.

---

## 🌟 Key Differentiators

Unlike generic AI chatbots that answer from broad internet data, **EduMind AI** strictly grounds its knowledge base in the individual professor's recorded lectures:
- **Zero-GPU Cloud Transcription**: Utilizes the Groq Whisper API (`whisper-large-v3-turbo`) to transcribe 60-minute lectures in under 30 seconds with word- and sentence-level timestamps.
- **Server Bandwidth Preservation**: Direct browser-to-cloud signed uploads to Cloudinary with real-time progress indicators, eliminating video file piping through application servers.
- **2048-Dimensional Dense Vector Retrieval**: Powered by NVIDIA Nemotron-3-Embed-1B for asymmetric semantic search.
- **Strict Multi-Tenant Course Isolation**: Qdrant vector database queries enforce metadata filtering (`course_id == requested_course_id`), ensuring students never retrieve chunks from unauthorized courses.
- **LangGraph Query Lifecycle Machine**: StateGraph orchestrates Guardrails (prompt-injection defense), Contextualization (pronoun resolution), Similarity Thresholding (< 0.20 confidence cutoff), and Grounded Synthesis.
- **Interactive Video Player Synchronization**: Answers stream token-by-token via Server-Sent Events (SSE). Citations render as interactive badges (e.g., `Lecture 1 @ 00:18`). Clicking seeks the video player directly to that moment.

---

## 🏗️ Architecture & Component Stack

```
EduMind-AI/
├── backend/                       # Node.js Express Application Backend
│   ├── src/
│   │   ├── config/                # MongoDB & Cloudinary SDK configurations
│   │   ├── controllers/           # Auth, Course, Lecture, and Chat SSE proxy logic
│   │   ├── middleware/            # JWT Protect, RBAC, and Error Handlers
│   │   ├── models/                # User, Course, Lecture, TranscriptBlock, Conversation
│   │   ├── routes/                # Express API endpoints
│   │   ├── app.js                 # Express application setup
│   │   └── server.js              # Server entry point (:5001)
│   ├── package.json
│   └── .env.example
│
├── ai-service/                    # FastAPI AI Microservice (Python 3.11)
│   ├── app/
│   │   ├── api/v1/                # Health, Ingestion, and Chat SSE endpoints
│   │   ├── core/                  # Settings (Groq, NVIDIA, Qdrant config)
│   │   ├── schemas/               # Pydantic data validation schemas
│   │   ├── services/              # Groq Whisper, Nemotron embedder, Qdrant & MongoDB services
│   │   ├── workflows/             # LangGraph state machine & nodes (Guardrail, RAG, Answer)
│   │   └── main.py                # FastAPI entry point (:8000)
│   ├── requirements.txt
│   └── .env.example
│
└── frontend/                      # React 19 Client Application (Vite + Tailwind CSS)
    ├── src/
    │   ├── components/            # VideoPlayer, CitationBadge, UploadLectureModal, Navbar
    │   ├── context/               # AuthContext (JWT, session, user roles)
    │   ├── pages/                 # Login, Register, Dashboard, CourseDetail
    │   ├── services/              # Axios API client with interceptors
    │   ├── App.jsx                # Route definitions
    │   └── main.jsx
    ├── package.json
    └── vite.config.js             # Vite dev server (:3000)
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- **Node.js** (v18+) & **npm**
- **Python** (3.11+)
- **MongoDB** running locally (`mongodb://localhost:27017/edumind-ai`) or MongoDB Atlas
- **API Keys**:
  - `GROQ_API_KEY`: Free at [console.groq.com](https://console.groq.com) (Whisper STT + LLM)
  - `NVIDIA_API_KEY`: Free at [build.nvidia.com](https://build.nvidia.com) (Nemotron 2048-dim embeddings)
  - Cloudinary credentials (optional for video uploads): [cloudinary.com](https://cloudinary.com)

---

### 2. Starting the Primary Backend (Node.js)

```bash
cd backend
npm install
npm run dev
# Server running at: http://localhost:5001
```

---

### 3. Starting the AI Microservice (FastAPI)

```bash
cd ai-service
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# API & Docs running at: http://localhost:8000/docs
```

---

### 4. Starting the Frontend Client (React + Vite)

```bash
cd frontend
npm install
npm run dev
# Web application running at: http://localhost:3000
```

---

## 🧪 Comprehensive Verification Suites

The platform includes standalone test suites for each phase and an all-in-one master verification audit:

```bash
# Run the Master Verification Audit (All Phases 1 through 6)
ai-service/venv/bin/python scripts/verify_all.py

# Run individual phase tests:
ai-service/venv/bin/python scripts/verify_phase1.py   # Baseline & Microservice Health
ai-service/venv/bin/python scripts/verify_phase2.py   # Cloud Audio & Groq Whisper STT
ai-service/venv/bin/python scripts/verify_phase3.py   # Semantic Chunks & Qdrant Isolation
ai-service/venv/bin/python scripts/verify_phase4.py   # LangGraph RAG & SSE Streaming
ai-service/venv/bin/python scripts/verify_phase5.py   # Video Player, Badges & Frontend
```

---

## 📊 Non-Functional Performance Benchmarks

| Metric | Target | Measured Result | Status |
| :--- | :--- | :--- | :--- |
| **Qdrant Retrieval Latency** | `< 100 ms` | **39.5 ms** | ✅ PASS |
| **Time to First Token (TTFT)** | `< 1.5 s` | **0.384 s** | ✅ PASS |
| **Zero Local GPU Overhead** | No local GPU required | 100% Cloud-native APIs | ✅ PASS |
| **Tenant Isolation** | Zero cross-course leakage | Metadata filtered by `course_id` | ✅ PASS |
