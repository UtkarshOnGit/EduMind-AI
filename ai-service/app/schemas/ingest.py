from pydantic import BaseModel, HttpUrl
from typing import List, Optional

class LectureIngestRequest(BaseModel):
    lecture_id: str
    course_id: str
    title: str
    cloudinary_url: str

class TranscriptSegment(BaseModel):
    block_index: int
    start_time: float
    end_time: float
    text: str

class IngestionStatusResponse(BaseModel):
    lecture_id: str
    status: str
    message: str
    total_blocks: Optional[int] = 0

class DirectChunkItem(BaseModel):
    start_time: float
    end_time: float
    text: str

class DirectChunksIngestRequest(BaseModel):
    course_id: str
    lecture_id: str
    lecture_title: str
    chunks: List[DirectChunkItem]
