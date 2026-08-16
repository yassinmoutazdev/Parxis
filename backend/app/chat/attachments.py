"""Chat message attachment handling (Epic B).

Attachments are ephemeral, single-turn context: parsed here and stored
against the ChatMessage they're attached to. They are never fed into the
vault-watcher/ingestion pipeline and never produce learning_item/
learning_correction/tracked note records -- they exist only inside the
chat message they're attached to.
"""

import base64
import io
import logging
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.config import settings
from app.db.models.chat import AttachmentKind

logger = logging.getLogger(__name__)

MAX_ATTACHMENT_SIZE_BYTES = 10 * 1024 * 1024  # 10MB per file
SUPPORTED_DOCUMENT_EXTENSIONS = {".txt", ".md", ".pdf", ".docx"}


def _resolve_kind(file: UploadFile) -> AttachmentKind:
    """Determine the attachment kind for an upload, or reject unsupported types.

    Images are recognized by content-type; text/markdown/PDF/DOCX are
    recognized by filename extension (browsers send inconsistent
    content-types for these, so the extension is the reliable signal).

    Args:
        file: The uploaded file

    Returns:
        The resolved AttachmentKind

    Raises:
        HTTPException: 400 if the file's type isn't in the supported list
    """
    content_type = (file.content_type or "").lower()
    ext = Path(file.filename or "").suffix.lower()

    if content_type.startswith("image/"):
        return AttachmentKind.IMAGE
    if ext in SUPPORTED_DOCUMENT_EXTENSIONS:
        return AttachmentKind.TEXT

    raise HTTPException(
        status_code=400,
        detail=(
            f"Unsupported attachment type for '{file.filename or 'file'}'. "
            "Supported types: .txt, .md, .pdf, .docx, and images."
        ),
    )


def _extract_text(ext: str, data: bytes) -> str:
    """Extract text content from a text/markdown/PDF/DOCX attachment's bytes.

    Args:
        ext: Lowercased file extension (".txt", ".md", ".pdf", or ".docx")
        data: Raw file bytes

    Returns:
        Extracted plain text
    """
    if ext in (".txt", ".md"):
        return data.decode("utf-8", errors="replace")

    if ext == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages).strip()

    if ext == ".docx":
        import docx

        document = docx.Document(io.BytesIO(data))
        return "\n".join(p.text for p in document.paragraphs).strip()

    raise ValueError(f"Unsupported document extension: {ext}")


async def process_attachment(
    file: UploadFile,
) -> tuple[AttachmentKind, str | None, str | None]:
    """Validate, size-check, and process a single uploaded attachment.

    Text/markdown/PDF/DOCX attachments are read directly into extracted
    text. Images are saved as-is to the local chat attachments directory
    (no extraction -- the configured Ollama model is multimodal and
    handles images natively).

    Args:
        file: The uploaded file

    Returns:
        (kind, extracted_text, stored_path) -- extracted_text is populated
        for text-kind attachments, stored_path for image-kind ones.

    Raises:
        HTTPException: 400 for unsupported types, oversized files, or
            unreadable/corrupted documents
    """
    kind = _resolve_kind(file)

    data = await file.read()
    if len(data) > MAX_ATTACHMENT_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"'{file.filename}' is too large "
                f"({len(data) / (1024 * 1024):.1f}MB). Max size is 10MB."
            ),
        )

    if kind == AttachmentKind.IMAGE:
        settings.chat_attachments_dir.mkdir(parents=True, exist_ok=True)
        ext = Path(file.filename or "").suffix or ".bin"
        stored_name = f"{uuid.uuid4().hex}{ext}"
        stored_path = settings.chat_attachments_dir / stored_name
        stored_path.write_bytes(data)
        return kind, None, str(stored_path)

    ext = Path(file.filename or "").suffix.lower()
    try:
        extracted_text = _extract_text(ext, data)
    except Exception as e:
        logger.error(f"Failed to extract text from attachment {file.filename}: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Could not read '{file.filename}' -- the file may be corrupted.",
        )

    return kind, extracted_text, None


def read_image_base64(stored_path: str) -> str:
    """Read a stored image attachment and return its base64-encoded bytes.

    Args:
        stored_path: Path to the stored image file

    Returns:
        Base64-encoded image bytes (no data-URI prefix), ready for Ollama's
        per-message `images` field
    """
    return base64.b64encode(Path(stored_path).read_bytes()).decode("ascii")
