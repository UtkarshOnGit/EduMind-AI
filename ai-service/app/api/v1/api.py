from fastapi import APIRouter
from app.api.v1.endpoints import health, ingest, chat

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(ingest.router, prefix="/ingest", tags=["Ingestion"])
api_router.include_router(chat.router, prefix="/chat", tags=["Chat & RAG"])
