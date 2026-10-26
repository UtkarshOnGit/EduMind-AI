import os
import logging
from typing import List, Dict, Any, Optional
from groq import Groq
from app.core.config import settings

logger = logging.getLogger("ai_service.transcription")

class TranscriptionService:
    """
    Zero-GPU Speech-to-Text service using Groq Whisper API (whisper-large-v3-turbo).
    Produces word- and sentence-level timestamped transcript blocks.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GROQ_API_KEY
        self._client: Optional[Groq] = None

    @property
    def client(self) -> Groq:
        if self._client is None:
            if not self.api_key:
                raise ValueError("GROQ_API_KEY is not configured in settings or environment.")
            self._client = Groq(api_key=self.api_key)
        return self._client

    def transcribe_file(self, audio_file_path: str, model: str = "whisper-large-v3-turbo") -> Dict[str, Any]:
        """
        Transcribes an audio file (.mp3, .wav, etc.) using Groq Whisper API.
        Returns full text, metadata, and timestamped blocks.
        """
        if not os.path.exists(audio_file_path):
            raise FileNotFoundError(f"Audio file not found: {audio_file_path}")

        file_size_mb = os.path.getsize(audio_file_path) / (1024 * 1024)
        logger.info(f"Submitting audio file ({file_size_mb:.2f} MB) to Groq Whisper API ({model})...")

        filename = os.path.basename(audio_file_path)
        with open(audio_file_path, "rb") as f:
            audio_bytes = f.read()

        response = self.client.audio.transcriptions.create(
            file=(filename, audio_bytes),
            model=model,
            response_format="verbose_json",
            temperature=0.0
        )

        # Parse segments into structured transcript blocks
        blocks: List[Dict[str, Any]] = []
        raw_segments = getattr(response, "segments", None)
        full_text = getattr(response, "text", "") or ""

        # Response might be a dict or a Pydantic object
        if raw_segments is None and isinstance(response, dict):
            raw_segments = response.get("segments", [])
            full_text = response.get("text", "")

        if raw_segments:
            for idx, seg in enumerate(raw_segments):
                if isinstance(seg, dict):
                    start = float(seg.get("start", 0.0))
                    end = float(seg.get("end", 0.0))
                    text = str(seg.get("text", "")).strip()
                else:
                    start = float(getattr(seg, "start", 0.0))
                    end = float(getattr(seg, "end", 0.0))
                    text = str(getattr(seg, "text", "")).strip()

                if text:
                    blocks.append({
                        "block_index": idx,
                        "start_time": round(start, 2),
                        "end_time": round(end, 2),
                        "text": text
                    })
        elif full_text:
            # Fallback if no granular segments were returned
            blocks.append({
                "block_index": 0,
                "start_time": 0.0,
                "end_time": round(getattr(response, "duration", 0.0) or 0.0, 2),
                "text": full_text.strip()
            })

        duration = getattr(response, "duration", None)
        if duration is None and isinstance(response, dict):
            duration = response.get("duration", 0.0)
        if not duration and blocks:
            duration = blocks[-1]["end_time"]

        logger.info(
            f"Groq Whisper transcription completed: {len(blocks)} blocks generated. "
            f"Total duration: {duration or 0.0:.2f}s"
        )

        return {
            "full_text": full_text,
            "duration": float(duration or 0.0),
            "language": getattr(response, "language", "en") if not isinstance(response, dict) else response.get("language", "en"),
            "blocks": blocks
        }

transcription_service = TranscriptionService()
