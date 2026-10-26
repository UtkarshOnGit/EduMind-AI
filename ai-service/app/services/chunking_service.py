import logging
import uuid
from typing import List, Dict, Any, Optional

logger = logging.getLogger("ai_service.chunking")

class ChunkingService:
    """
    Semantic text chunker for timestamped lecture transcripts.
    Merges sentence/segment-level transcript blocks into cohesive semantic chunks
    (300-500 tokens with overlap), preserving aggregate start and end timestamps.
    """

    def __init__(
        self,
        target_tokens: int = 350,
        min_tokens: int = 150,
        max_tokens: int = 500,
        overlap_tokens: int = 60
    ):
        self.target_tokens = target_tokens
        self.min_tokens = min_tokens
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """
        Heuristic approximation: 1 token ~= 0.75 words, or len(words) * 1.33.
        Whitespace splitting + subword multiplier.
        """
        words = text.strip().split()
        return max(1, int(len(words) * 1.3))

    def chunk_transcript(
        self,
        blocks: List[Dict[str, Any]],
        course_id: str,
        lecture_id: str,
        lecture_title: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Groups transcript blocks into timestamp-preserved semantic chunks with overlap.
        """
        if not blocks:
            logger.warning(f"No transcript blocks provided for lecture {lecture_id}")
            return []

        chunks: List[Dict[str, Any]] = []
        current_blocks: List[Dict[str, Any]] = []
        current_tokens = 0
        chunk_index = 0

        for block in blocks:
            text = block.get("text", "").strip()
            if not text:
                continue

            block_tokens = self.estimate_tokens(text)
            current_blocks.append(block)
            current_tokens += block_tokens

            # If we reached our target token size
            if current_tokens >= self.target_tokens:
                chunk = self._create_chunk(
                    chunk_index=chunk_index,
                    blocks=current_blocks,
                    course_id=course_id,
                    lecture_id=lecture_id,
                    lecture_title=lecture_title
                )
                chunks.append(chunk)
                chunk_index += 1

                # Prepare overlap blocks for next chunk
                overlap_acc_tokens = 0
                next_blocks = []
                for b in reversed(current_blocks):
                    b_tok = self.estimate_tokens(b.get("text", ""))
                    if overlap_acc_tokens + b_tok <= self.overlap_tokens or not next_blocks:
                        next_blocks.insert(0, b)
                        overlap_acc_tokens += b_tok
                    else:
                        break

                current_blocks = next_blocks
                current_tokens = sum(self.estimate_tokens(b.get("text", "")) for b in current_blocks)

        # Handle remaining blocks
        if current_blocks:
            # If we already have chunks and the leftover is very small, merge with the last chunk
            if chunks and current_tokens < self.min_tokens:
                last_chunk = chunks[-1]
                additional_text = " " + " ".join(b.get("text", "").strip() for b in current_blocks)
                last_chunk["text"] += additional_text
                last_chunk["end_time"] = round(float(current_blocks[-1].get("end_time", last_chunk["end_time"])), 2)
                last_chunk["token_count"] = self.estimate_tokens(last_chunk["text"])
            else:
                chunk = self._create_chunk(
                    chunk_index=chunk_index,
                    blocks=current_blocks,
                    course_id=course_id,
                    lecture_id=lecture_id,
                    lecture_title=lecture_title
                )
                chunks.append(chunk)

        logger.info(
            f"Chunked lecture {lecture_id} ({len(blocks)} blocks) into {len(chunks)} semantic chunks. "
            f"Avg tokens/chunk: {sum(c['token_count'] for c in chunks) / max(1, len(chunks)):.1f}"
        )
        return chunks

    def _create_chunk(
        self,
        chunk_index: int,
        blocks: List[Dict[str, Any]],
        course_id: str,
        lecture_id: str,
        lecture_title: str
    ) -> Dict[str, Any]:
        start_time = round(float(blocks[0].get("start_time", 0.0)), 2)
        end_time = round(float(blocks[-1].get("end_time", start_time)), 2)
        combined_text = " ".join(b.get("text", "").strip() for b in blocks)

        return {
            "chunk_id": f"{lecture_id}_c{chunk_index}",
            "course_id": course_id,
            "lecture_id": lecture_id,
            "lecture_title": lecture_title,
            "chunk_index": chunk_index,
            "start_time": start_time,
            "end_time": end_time,
            "text": combined_text,
            "token_count": self.estimate_tokens(combined_text)
        }

chunking_service = ChunkingService()
