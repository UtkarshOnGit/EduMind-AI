import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.api import api_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("edumind_ai")

app = FastAPI(
    title="Edumind AI Engine",
    description="Dedicated AI Microservice for Edumind AI - Groq Whisper STT, Nemotron-3-Embed-1B, Qdrant Vector Search & LangGraph Workflows",
    version="1.0.0"
)

# Enable CORS for frontend and Node backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API v1 router
app.include_router(api_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {
        "name": "Edumind AI Microservice",
        "version": "1.0.0",
        "docs_url": "/docs",
        "status": "healthy"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
