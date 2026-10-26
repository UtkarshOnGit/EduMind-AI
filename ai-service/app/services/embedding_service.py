import logging
import httpx
from typing import List, Optional
from app.core.config import settings

logger = logging.getLogger("ai_service.embeddings")

class EmbeddingService:
    """
    Semantic text embedding service powered by NVIDIA Nemotron-3-Embed-1B.
    Generates 2048-dimensional dense vectors optimized for asymmetric RAG retrieval.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.api_key = api_key or settings.NVIDIA_API_KEY
        self.base_url = (base_url or settings.NVIDIA_BASE_URL).rstrip("/")
        self.model = model or settings.NVIDIA_EMBED_MODEL
        self.dimension = settings.VECTOR_DIMENSION

    def _get_headers(self) -> dict:
        if not self.api_key:
            raise ValueError("NVIDIA_API_KEY is not configured in settings or environment.")
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def embed_passages(self, texts: List[str], batch_size: int = 16) -> List[List[float]]:
        """
        Embeds a list of lecture chunk passages using input_type='passage'.
        Batches requests to respect API rate and payload limits.
        """
        if not texts:
            return []

        all_embeddings: List[List[float]] = []
        endpoint = f"{self.base_url}/embeddings"
        headers = self._get_headers()

        logger.info(f"Generating embeddings for {len(texts)} chunks using {self.model} (batch size: {batch_size})...")

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            payload = {
                "input": batch,
                "model": self.model,
                "input_type": "passage",
                "encoding_format": "float",
                "truncate": "END"
            }

            with httpx.Client(timeout=30.0) as client:
                res = client.post(endpoint, json=payload, headers=headers)
                if res.status_code != 200:
                    err_msg = f"NVIDIA Embedding API error ({res.status_code}): {res.text}"
                    logger.error(err_msg)
                    raise RuntimeError(err_msg)

                data = res.json().get("data", [])
                # Ensure ordered by index
                sorted_batch = sorted(data, key=lambda x: x.get("index", 0))
                for item in sorted_batch:
                    embedding = item.get("embedding", [])
                    if len(embedding) != self.dimension:
                        logger.warning(f"Unexpected embedding dimension: got {len(embedding)}, expected {self.dimension}")
                    all_embeddings.append(embedding)

        logger.info(f"Successfully generated {len(all_embeddings)} embeddings ({self.dimension}-dim).")
        return all_embeddings

    def embed_query(self, query: str) -> List[float]:
        """
        Embeds a search query using input_type='query' for asymmetric semantic search.
        """
        if not query or not query.strip():
            raise ValueError("Query string cannot be empty.")

        endpoint = f"{self.base_url}/embeddings"
        headers = self._get_headers()
        payload = {
            "input": [query.strip()],
            "model": self.model,
            "input_type": "query",
            "encoding_format": "float",
            "truncate": "END"
        }

        with httpx.Client(timeout=15.0) as client:
            res = client.post(endpoint, json=payload, headers=headers)
            if res.status_code != 200:
                err_msg = f"NVIDIA Embedding API query error ({res.status_code}): {res.text}"
                logger.error(err_msg)
                raise RuntimeError(err_msg)

            data = res.json().get("data", [])
            if not data:
                raise RuntimeError("No embedding returned for query.")
            return data[0]["embedding"]

embedding_service = EmbeddingService()
