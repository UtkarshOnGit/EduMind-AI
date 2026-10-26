import os
import uuid
import logging
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models
from app.core.config import settings

logger = logging.getLogger("ai_service.qdrant")

class QdrantService:
    """
    Qdrant Vector Database service.
    Handles collection initialization, payload indexing, batch upserting,
    and strict multi-tenant course-isolated similarity search.
    """

    def __init__(self):
        self.collection_name = settings.QDRANT_COLLECTION_NAME
        self.dimension = settings.VECTOR_DIMENSION
        self._client: Optional[QdrantClient] = None

    @property
    def client(self) -> QdrantClient:
        if self._client is None:
            self._client = self._initialize_client()
        return self._client

    def _initialize_client(self) -> QdrantClient:
        """
        Attempts to connect to external Qdrant URL.
        If unavailable, falls back gracefully to embedded local disk persistence.
        """
        if settings.QDRANT_URL and settings.QDRANT_URL.startswith("http"):
            try:
                c = QdrantClient(
                    url=settings.QDRANT_URL,
                    api_key=settings.QDRANT_API_KEY,
                    timeout=2.0,
                    check_compatibility=False
                )
                # Verify connectivity
                c.get_collections()
                logger.info(f"Connected to remote Qdrant server at: {settings.QDRANT_URL}")
                return c
            except Exception as e:
                logger.warning(
                    f"Unable to connect to remote Qdrant at {settings.QDRANT_URL} ({e}). "
                    f"Falling back to embedded local storage at '{settings.QDRANT_STORAGE_PATH}'."
                )

        raw_storage_path = settings.QDRANT_STORAGE_PATH or "./qdrant_storage"
        if not os.path.isabs(raw_storage_path):
            storage_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..", raw_storage_path)
            )
        else:
            storage_path = raw_storage_path
        os.makedirs(storage_path, exist_ok=True)
        c = QdrantClient(path=storage_path)
        logger.info(f"Using embedded Qdrant with local persistence at: {storage_path}")
        return c

    def close(self):
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

    def ensure_collection(self, collection_name: Optional[str] = None):
        """
        Ensures the vector collection exists with 2048 dimensions (Cosine distance)
        and creates payload indexes for fast course_id and lecture_id filtering.
        """
        col_name = collection_name or self.collection_name
        try:
            collections = self.client.get_collections().collections
            exists = any(c.name == col_name for c in collections)
        except Exception:
            exists = False

        if not exists:
            logger.info(f"Creating Qdrant collection '{col_name}' (dim: {self.dimension}, distance: Cosine)...")
            self.client.create_collection(
                collection_name=col_name,
                vectors_config=models.VectorParams(
                    size=self.dimension,
                    distance=models.Distance.COSINE
                )
            )

            # Create payload indexes on course_id and lecture_id for fast filtering
            try:
                self.client.create_payload_index(
                    collection_name=col_name,
                    field_name="course_id",
                    field_schema=models.PayloadSchemaType.KEYWORD
                )
                self.client.create_payload_index(
                    collection_name=col_name,
                    field_name="lecture_id",
                    field_schema=models.PayloadSchemaType.KEYWORD
                )
                logger.info(f"Payload indexes created on 'course_id' and 'lecture_id' for {col_name}")
            except Exception as idx_err:
                logger.debug(f"Payload index creation note: {idx_err}")
        else:
            logger.info(f"Qdrant collection '{col_name}' already exists.")

    def upsert_chunks(
        self,
        chunks: List[Dict[str, Any]],
        embeddings: List[List[float]],
        collection_name: Optional[str] = None
    ) -> int:
        """
        Upserts chunk vectors and payload metadata into Qdrant collection.
        """
        if not chunks or not embeddings:
            logger.warning("No chunks or embeddings provided to upsert.")
            return 0

        if len(chunks) != len(embeddings):
            raise ValueError(f"Mismatch: {len(chunks)} chunks vs {len(embeddings)} embeddings.")

        col_name = collection_name or self.collection_name
        self.ensure_collection(col_name)

        points = []
        for chunk, vector in zip(chunks, embeddings):
            # Deterministic UUID from chunk_id
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, str(chunk["chunk_id"])))
            payload = {
                "chunk_id": chunk["chunk_id"],
                "course_id": str(chunk["course_id"]),
                "lecture_id": str(chunk["lecture_id"]),
                "lecture_title": chunk.get("lecture_title", ""),
                "chunk_index": chunk.get("chunk_index", 0),
                "start_time": float(chunk["start_time"]),
                "end_time": float(chunk["end_time"]),
                "text": chunk["text"],
                "token_count": chunk.get("token_count", 0)
            }

            points.append(
                models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload
                )
            )

        self.client.upsert(
            collection_name=col_name,
            points=points
        )

        logger.info(f"Successfully upserted {len(points)} vector points into Qdrant collection '{col_name}'.")
        return len(points)

    def search_course_chunks(
        self,
        course_id: str,
        query_vector: List[float],
        limit: int = 5,
        score_threshold: Optional[float] = None,
        collection_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Performs vector similarity search strictly filtered by course_id.
        Guarantees multi-tenant isolation across courses.
        """
        col_name = collection_name or self.collection_name
        self.ensure_collection(col_name)

        course_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="course_id",
                    match=models.MatchValue(value=str(course_id))
                )
            ]
        )

        # Support both query_points (newer) and search (older)
        if hasattr(self.client, "query_points"):
            response = self.client.query_points(
                collection_name=col_name,
                query=query_vector,
                query_filter=course_filter,
                limit=limit,
                score_threshold=score_threshold
            )
            raw_points = response.points
        else:
            raw_points = self.client.search(
                collection_name=col_name,
                query_vector=query_vector,
                query_filter=course_filter,
                limit=limit,
                score_threshold=score_threshold
            )

        results = []
        for pt in raw_points:
            p = pt.payload or {}
            results.append({
                "chunk_id": p.get("chunk_id"),
                "course_id": p.get("course_id"),
                "lecture_id": p.get("lecture_id"),
                "lecture_title": p.get("lecture_title", ""),
                "start_time": p.get("start_time"),
                "end_time": p.get("end_time"),
                "text": p.get("text", ""),
                "score": round(float(pt.score), 4)
            })

        logger.info(
            f"Retrieved {len(results)} chunks for course {course_id} "
            f"(threshold: {score_threshold or 'none'})"
        )
        return results

qdrant_service = QdrantService()
