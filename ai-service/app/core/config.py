import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # Groq API for Whisper STT
    GROQ_API_KEY: Optional[str] = None

    # NVIDIA API for Nemotron-3-Embed-1B
    NVIDIA_API_KEY: Optional[str] = None
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_EMBED_MODEL: str = "nvidia/nemotron-3-embed-1b"

    # Google Gemini API (Optional native Gemini integration)
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_LLM_MODEL: str = "gemini-3.8-flash"

    # LLM Settings for LangGraph Agent
    LLM_PROVIDER: str = "groq"  # "gemini" | "groq" | "nvidia" | "openai"
    GROQ_LLM_MODEL: str = "qwen/qwen3.8-27b"
    NVIDIA_LLM_MODEL: str = "meta/llama-3.2-11b-vision-instruct"
    LLM_TEMPERATURE: float = 0.3
    SIMILARITY_THRESHOLD: float = 0.20

    # Qdrant Vector DB
    QDRANT_URL: Optional[str] = "http://localhost:6333"
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_COLLECTION_NAME: str = "edumind_course_transcripts"
    QDRANT_STORAGE_PATH: Optional[str] = "./qdrant_storage"
    VECTOR_DIMENSION: int = 2048

    # MongoDB
    MONGODB_URI: str = "mongodb://localhost:27017/edumind-ai"

    # Node.js Backend URL (for callbacks/webhooks)
    BACKEND_URL: str = "http://localhost:5001"

    model_config = SettingsConfigDict(
        env_file=(
            os.path.join(os.path.dirname(__file__), "..", "..", ".env"),
            ".env",
            os.path.join(os.getcwd(), "ai-service", ".env")
        ),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
