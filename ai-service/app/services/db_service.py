import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
import httpx
from pymongo import MongoClient, UpdateOne
from bson import ObjectId
from app.core.config import settings

logger = logging.getLogger("ai_service.db")

class DBService:
    """
    Handles MongoDB persistence for transcript blocks and lecture statuses,
    as well as webhook callbacks to the Node.js backend.
    """

    def __init__(self, uri: Optional[str] = None):
        self.uri = uri or settings.MONGODB_URI
        self._client: Optional[MongoClient] = None
        self._db = None

    @property
    def db(self):
        if self._db is None:
            self._client = MongoClient(self.uri, serverSelectionTimeoutMS=5000)
            # Parse DB name from URI or use default
            db_name = "edumind-ai"
            try:
                parsed_db = self._client.get_default_database()
                if parsed_db is not None:
                    db_name = parsed_db.name
            except Exception:
                pass
            self._db = self._client[db_name]
            logger.info(f"Connected to MongoDB database: {db_name}")
        return self._db

    def update_lecture_status(
        self,
        lecture_id: str,
        status: str,
        processing_error: Optional[str] = None,
        duration: Optional[float] = None
    ) -> bool:
        """
        Updates the lecture record status directly in MongoDB.
        """
        try:
            update_fields: Dict[str, Any] = {
                "status": status,
                "updatedAt": datetime.utcnow()
            }
            if processing_error is not None:
                update_fields["processingError"] = processing_error
            elif status == "processed":
                update_fields["processingError"] = None

            if duration is not None and duration > 0:
                update_fields["duration"] = round(duration, 2)

            res = self.db.lectures.update_one(
                {"_id": ObjectId(lecture_id)},
                {"$set": update_fields}
            )
            logger.info(f"Updated lecture {lecture_id} status in MongoDB to '{status}' (matched: {res.matched_count})")
            return res.matched_count > 0
        except Exception as e:
            logger.error(f"Failed to update lecture status in MongoDB for {lecture_id}: {e}")
            return False

    def save_transcript_blocks(
        self,
        course_id: str,
        lecture_id: str,
        blocks: List[Dict[str, Any]]
    ) -> int:
        """
        Bulk upserts raw transcript blocks to MongoDB transcriptblocks collection.
        Provides fault-tolerant incremental persistence.
        """
        if not blocks:
            logger.warning(f"No transcript blocks to persist for lecture {lecture_id}")
            return 0

        try:
            c_oid = ObjectId(course_id)
            l_oid = ObjectId(lecture_id)
            now = datetime.utcnow()

            operations = []
            for b in blocks:
                block_index = int(b["block_index"])
                doc = {
                    "courseId": c_oid,
                    "lectureId": l_oid,
                    "blockIndex": block_index,
                    "startTime": float(b["start_time"]),
                    "endTime": float(b["end_time"]),
                    "text": str(b["text"]),
                    "updatedAt": now
                }
                operations.append(
                    UpdateOne(
                        {"lectureId": l_oid, "blockIndex": block_index},
                        {"$set": doc, "$setOnInsert": {"createdAt": now}},
                        upsert=True
                    )
                )

            if operations:
                result = self.db.transcriptblocks.bulk_write(operations, ordered=False)
                upserted = (result.upserted_count or 0) + (result.modified_count or 0)
                logger.info(
                    f"Saved {len(blocks)} transcript blocks to MongoDB for lecture {lecture_id} (upserted: {upserted})"
                )
                return len(blocks)
            return 0
        except Exception as e:
            logger.error(f"Failed to save transcript blocks to MongoDB for lecture {lecture_id}: {e}")
            raise e

    def get_transcript_blocks(self, lecture_id: str) -> List[Dict[str, Any]]:
        """
        Fetches all transcript blocks for a given lecture, ordered by blockIndex.
        """
        try:
            cursor = self.db.transcriptblocks.find(
                {"lectureId": ObjectId(lecture_id)}
            ).sort("blockIndex", 1)

            results = []
            for doc in cursor:
                doc["_id"] = str(doc["_id"])
                doc["lectureId"] = str(doc["lectureId"])
                doc["courseId"] = str(doc["courseId"])
                results.append(doc)
            return results
        except Exception as e:
            logger.error(f"Error fetching transcript blocks for lecture {lecture_id}: {e}")
            return []

    async def notify_backend(
        self,
        lecture_id: str,
        status: str,
        processing_error: Optional[str] = None,
        transcript_blocks: Optional[List[Dict[str, Any]]] = None
    ):
        """
        Sends callback notification to Node.js backend PATCH /api/v1/lectures/:lectureId/status.
        """
        url = f"{settings.BACKEND_URL}/api/v1/lectures/{lecture_id}/status"
        payload = {
            "status": status,
            "processingError": processing_error
        }
        if transcript_blocks:
            payload["transcriptBlocks"] = [
                {
                    "blockIndex": b["block_index"],
                    "startTime": b["start_time"],
                    "endTime": b["end_time"],
                    "text": b["text"]
                }
                for b in transcript_blocks
            ]

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.patch(url, json=payload)
                if res.status_code == 200:
                    logger.info(f"Node.js backend notified successfully for lecture {lecture_id} ({status})")
                else:
                    logger.warning(
                        f"Node.js backend callback returned status {res.status_code} for lecture {lecture_id}"
                    )
        except Exception as err:
            logger.warning(f"Could not reach Node.js backend callback at {url}: {err}")

db_service = DBService()
