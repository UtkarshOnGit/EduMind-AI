from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class MessageHistoryItem(BaseModel):
    sender: str
    text: str

class ChatQueryRequest(BaseModel):
    course_id: str
    student_id: str
    conversation_id: Optional[str] = None
    query: str
    history: Optional[List[MessageHistoryItem]] = []

class Citation(BaseModel):
    lecture_id: str
    lecture_title: Optional[str] = None
    start_time: float
    end_time: float
    chunk_text: str
    score: float
