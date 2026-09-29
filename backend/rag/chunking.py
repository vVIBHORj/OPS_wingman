"""Deterministic Document Chunking Utilities (Phase 3 - Deliverable D-10)."""

import re
from typing import Any, Dict, List


class DocumentChunkDict(dict):
    """Dictionary subclass allowing attribute-style access (e.g. chunk.chunk_index)."""

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"'DocumentChunkDict' object has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value

    @property
    def text(self) -> str:
        return self.get("chunk_text", "")


def chunk_document(
    content: str,
    max_chunk_size: int = 600,
    overlap: int = 100,
) -> List[DocumentChunkDict]:
    """Deterministically splits markdown or text documents into semantic chunks

    preserving section context, headers, and bullet points.
    """
    cleaned = content.strip()
    if not cleaned:
        return []

    # 1. Split into natural sections / paragraphs
    raw_sections = re.split(r"\n\s*\n", cleaned)
    sections: List[str] = [s.strip() for s in raw_sections if s.strip()]

    chunks: List[DocumentChunkDict] = []
    current_chunk = ""
    current_header = "General"
    chunk_index = 0

    for section in sections:
        # Detect markdown headers
        header_match = re.match(r"^(#{1,4}\s+.*)", section)
        if header_match:
            current_header = header_match.group(1).lstrip("#").strip()

        # If appending section exceeds max_chunk_size and current_chunk is not empty
        if len(current_chunk) + len(section) > max_chunk_size and current_chunk:
            chunks.append(
                DocumentChunkDict(
                    chunk_text=current_chunk.strip(),
                    chunk_index=chunk_index,
                    metadata={"section_header": current_header, "char_length": len(current_chunk.strip())},
                )
            )
            chunk_index += 1
            # Maintain overlap from end of current chunk
            overlap_text = current_chunk[-overlap:] if len(current_chunk) > overlap else ""
            current_chunk = overlap_text + "\n" + section
        else:
            if current_chunk:
                current_chunk += "\n\n" + section
            else:
                current_chunk = section

    if current_chunk.strip():
        chunks.append(
            DocumentChunkDict(
                chunk_text=current_chunk.strip(),
                chunk_index=chunk_index,
                metadata={"section_header": current_header, "char_length": len(current_chunk.strip())},
            )
        )

    return chunks
