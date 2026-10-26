import os
import re
import tempfile
import logging
import httpx
from typing import Optional

logger = logging.getLogger("ai_service.media")

class MediaService:
    """
    Handles media processing and cloud audio transformation.
    Extracts audio stream (.mp3) from video URLs (Cloudinary or generic)
    without downloading multi-gigabyte video files.
    """

    @staticmethod
    def get_audio_transformation_url(cloudinary_url: str, target_format: str = "mp3") -> str:
        """
        Converts a Cloudinary video URL to an optimized audio stream URL.
        Example:
        https://res.cloudinary.com/demo/video/upload/v1234/sample.mp4
        ->
        https://res.cloudinary.com/demo/video/upload/f_mp3/v1234/sample.mp3
        """
        if not cloudinary_url:
            return ""

        url = cloudinary_url.strip()

        # If already an audio format, return as is
        if re.search(r'\.(mp3|wav|m4a|aac|ogg)(\?.*)?$', url, re.IGNORECASE):
            return url

        # Check if it's a Cloudinary URL
        if "cloudinary.com" in url:
            # Replace video extension with target audio format
            transformed = re.sub(r'\.(mp4|mov|mkv|webm|avi|flv)(\?.*)?$', f'.{target_format}', url, flags=re.IGNORECASE)

            # Inject format flag /f_mp3/ if upload/ is present and flag is not yet added
            if "/upload/" in transformed and f"/f_{target_format}/" not in transformed:
                transformed = transformed.replace("/upload/", f"/upload/f_{target_format}/", 1)

            logger.info(f"Transformed Cloudinary video URL to audio: {transformed}")
            return transformed

        # Generic URL fallback
        return url

    @staticmethod
    async def download_audio_stream(audio_url: str, output_path: Optional[str] = None) -> str:
        """
        Streams audio file from URL directly to a temporary file.
        Returns the path to the downloaded audio file.
        """
        if not output_path:
            fd, output_path = tempfile.mkstemp(suffix=".mp3", prefix="edumind_audio_")
            os.close(fd)

        logger.info(f"Streaming audio track from: {audio_url} to {output_path}")

        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            async with client.stream("GET", audio_url) as response:
                if response.status_code >= 400:
                    raise RuntimeError(
                        f"Failed to fetch audio stream. Status code: {response.status_code}, URL: {audio_url}"
                    )
                with open(output_path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=1024 * 64):
                        f.write(chunk)

        file_size_kb = os.path.getsize(output_path) / 1024
        logger.info(f"Audio downloaded successfully ({file_size_kb:.2f} KB): {output_path}")
        return output_path

media_service = MediaService()
