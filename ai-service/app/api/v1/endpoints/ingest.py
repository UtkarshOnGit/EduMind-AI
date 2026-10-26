import os
import logging
import traceback
from typing import List, Dict, Any
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from app.schemas.ingest import (
    LectureIngestRequest,
    IngestionStatusResponse,
    TranscriptSegment,
    DirectChunksIngestRequest
)
from app.services.media_service import media_service
from app.services.transcription_service import transcription_service
from app.services.db_service import db_service
from app.services.chunking_service import chunking_service
from app.services.embedding_service import embedding_service
from app.services.qdrant_service import qdrant_service

logger = logging.getLogger("ai_service.ingest")
router = APIRouter()

async def process_lecture_pipeline(lecture_req: LectureIngestRequest):
    """
    End-to-End Background Ingestion Pipeline:
    1. Mark Lecture as 'processing' in DB
    2. Extract audio track from Cloudinary / media URL
    3. Transcribe via Groq Whisper API (whisper-large-v3-turbo)
    4. Save fault-tolerant raw transcript blocks to MongoDB
    5. Perform semantic chunking with overlap & timestamp preservation
    6. Generate 2048-dim embeddings via NVIDIA Nemotron-3-Embed-1B
    7. Upsert vectors & metadata into Qdrant (course-isolated)
    8. Update Lecture status to 'processed' and notify Node.js backend
    """
    lecture_id = lecture_req.lecture_id
    course_id = lecture_req.course_id
    audio_temp_path = None

    logger.info(f"=== Starting background ingestion for lecture {lecture_id} ({lecture_req.title}) ===")

    try:
        # Step 1: Mark status as 'processing'
        db_service.update_lecture_status(lecture_id, status="processing")
        await db_service.notify_backend(lecture_id, status="processing")

        # Step 2: Get audio transformation URL
        audio_url = media_service.get_audio_transformation_url(lecture_req.cloudinary_url)
        logger.info(f"Derived audio extraction URL: {audio_url}")

        # Step 3: Stream audio track to temporary file
        audio_temp_path = await media_service.download_audio_stream(audio_url)

        # Step 4: Transcribe using Groq Whisper API (whisper-large-v3-turbo)
        stt_result = transcription_service.transcribe_file(audio_temp_path)
        blocks = stt_result.get("blocks", [])
        duration = stt_result.get("duration", 0.0)

        logger.info(
            f"Transcription succeeded for lecture {lecture_id}: {len(blocks)} blocks, duration: {duration:.2f}s"
        )

        # Step 5: Fault-tolerant persistent storage of transcript blocks in MongoDB
        saved_count = db_service.save_transcript_blocks(course_id, lecture_id, blocks)
        db_service.update_lecture_status(lecture_id, status="processing", duration=duration)

        # Step 6: Semantic text chunking (300-500 tokens with overlap)
        chunks = chunking_service.chunk_transcript(
            blocks=blocks,
            course_id=course_id,
            lecture_id=lecture_id,
            lecture_title=lecture_req.title
        )
        logger.info(f"Produced {len(chunks)} semantic chunks for lecture {lecture_id}")

        if chunks:
            # Step 7: Generate 2048-dim embeddings via NVIDIA Nemotron-3-Embed-1B
            chunk_texts = [c["text"] for c in chunks]
            embeddings = embedding_service.embed_passages(chunk_texts)

            # Step 8: Upsert into Qdrant collection with course_id and lecture_id indexing
            upserted_count = qdrant_service.upsert_chunks(chunks, embeddings)
            logger.info(f"Upserted {upserted_count} vectors into Qdrant for lecture {lecture_id}")

        # Step 9: Finalize lecture status to 'processed'
        db_service.update_lecture_status(lecture_id, status="processed", duration=duration)

        # Step 10: Notify Node.js backend of final processed status
        await db_service.notify_backend(
            lecture_id=lecture_id,
            status="processed",
            transcript_blocks=blocks
        )

        logger.info(
            f"=== Ingestion complete for lecture {lecture_id}: status is 'processed' ==="
        )

    except Exception as exc:
        err_msg = f"{type(exc).__name__}: {str(exc)}"
        logger.error(f"Error in lecture ingestion pipeline for {lecture_id}: {err_msg}")
        logger.error(traceback.format_exc())

        # Update failure status in DB & notify Node.js
        db_service.update_lecture_status(lecture_id, status="failed", processing_error=err_msg)
        await db_service.notify_backend(lecture_id, status="failed", processing_error=err_msg)

    finally:
        # Clean up temporary audio file
        if audio_temp_path and os.path.exists(audio_temp_path):
            try:
                os.remove(audio_temp_path)
                logger.info(f"Cleaned up temporary audio file: {audio_temp_path}")
            except Exception as e:
                logger.warning(f"Failed to remove temp file {audio_temp_path}: {e}")

@router.post("/lecture", response_model=IngestionStatusResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_lecture(
    payload: LectureIngestRequest,
    background_tasks: BackgroundTasks
):
    """
    Trigger lecture audio extraction, transcription, and indexing.
    Returns 202 Accepted immediately and processes in the background.
    """
    logger.info(f"Received ingestion request for lecture: {payload.lecture_id} ({payload.title})")
    
    # Enqueue background task
    background_tasks.add_task(process_lecture_pipeline, payload)

    return IngestionStatusResponse(
        lecture_id=payload.lecture_id,
        status="processing",
        message="Lecture ingestion pipeline started in background",
        total_blocks=0
    )

@router.get("/lecture/{lecture_id}/transcript")
async def get_lecture_transcript(lecture_id: str):
    """
    Retrieve stored timestamped transcript blocks for a lecture from MongoDB.
    """
    blocks = db_service.get_transcript_blocks(lecture_id)
    if not blocks:
        raise HTTPException(status_code=404, detail="No transcript blocks found for this lecture.")
    return {
        "lecture_id": lecture_id,
        "count": len(blocks),
        "transcript_blocks": blocks
    }

@router.post("/chunks")
async def ingest_direct_chunks(payload: DirectChunksIngestRequest):
    """
    Directly ingest and index formatted lecture chunks into Qdrant & MongoDB.
    Useful for tutorial texts, pre-processed transcripts, and direct ingestion.
    """
    logger.info(f"Direct chunk ingestion received for course {payload.course_id}, lecture {payload.lecture_id} ({len(payload.chunks)} chunks)")

    # 1. Prepare chunks formatted for Qdrant
    prepared_chunks = []
    raw_blocks = []
    max_end_time = 0.0

    for idx, c in enumerate(payload.chunks):
        chunk_dict = {
            "chunk_id": f"{payload.lecture_id}_c{idx}",
            "course_id": payload.course_id,
            "lecture_id": payload.lecture_id,
            "lecture_title": payload.lecture_title,
            "chunk_index": idx,
            "start_time": c.start_time,
            "end_time": c.end_time,
            "text": c.text,
            "token_count": len(c.text.split())
        }
        prepared_chunks.append(chunk_dict)

        raw_blocks.append({
            "block_index": idx,
            "start_time": c.start_time,
            "end_time": c.end_time,
            "text": c.text
        })
        if c.end_time > max_end_time:
            max_end_time = c.end_time

    # 2. Save blocks to MongoDB
    db_service.save_transcript_blocks(payload.course_id, payload.lecture_id, raw_blocks)

    # 3. Generate 2048-dim embeddings via NVIDIA Nemotron
    chunk_texts = [c["text"] for c in prepared_chunks]
    embeddings = embedding_service.embed_passages(chunk_texts)

    # 4. Upsert into Qdrant
    upserted_count = qdrant_service.upsert_chunks(prepared_chunks, embeddings)

    # 5. Mark lecture as processed in MongoDB and notify Node
    db_service.update_lecture_status(payload.lecture_id, status="processed", duration=max_end_time)
    await db_service.notify_backend(
        lecture_id=payload.lecture_id,
        status="processed",
        transcript_blocks=raw_blocks
    )

    logger.info(f"Direct ingestion complete for lecture {payload.lecture_id}: {upserted_count} vectors indexed.")

    return {
        "success": True,
        "course_id": payload.course_id,
        "lecture_id": payload.lecture_id,
        "upserted_chunks": upserted_count,
        "duration": max_end_time
    }
