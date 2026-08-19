"""Chat API router.

Corresponds to PRAXIS_CHAT_COACH_PLAN Section 3.4 (first four endpoints) and Section 4.3 (remaining endpoints).
"""

import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.chat.attachments import MAX_ATTACHMENT_CONTEXT_CHARS, process_attachment
from app.chat.service import ChatService
from app.db.models.chat import (
    AttachmentKind,
    ChatActionType,
    ChatMessage,
    ChatRole,
    ChatThread,
)
from app.llm.ollama_adapter import reraise_known_ollama_error

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatThreadResponse(BaseModel):
    """Response for a chat thread (list/detail view)."""

    id: int
    title: str | None
    last_message_preview: str | None
    updated_at: datetime


class AttachmentResponse(BaseModel):
    """Response for a chat message attachment (Epic B)."""

    id: int
    filename: str
    kind: str
    mime_type: str
    context_truncated: bool


class ChatMessageResponse(BaseModel):
    """Response for a chat message."""

    id: int
    thread_id: int
    role: str
    content: str
    action_type: str
    action_ref_id: int | None
    created_at: datetime
    attachments: list[AttachmentResponse] | None = None


class ChatThreadDetailResponse(BaseModel):
    """Response for a chat thread with its messages."""

    id: int
    title: str | None
    created_at: datetime
    updated_at: datetime
    last_message_preview: str | None
    messages: list[ChatMessageResponse]


class SendMessageResponse(BaseModel):
    """Response for sending a message (returns both user and assistant messages)."""

    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse


class EditMessageRequest(BaseModel):
    """Request body for editing a user message (Epic A: edit-with-regenerate)."""

    content: str


class StartQuizDirectRequest(BaseModel):
    """Request body for the manual '+' quiz trigger (Work Item D).

    Bypasses the LLM entirely -- invokes the same start_quiz_action code
    path the tool-calling flow already uses, just triggered directly from
    the composer's "+" menu instead of a model decision.
    """

    size: int = 10


class StartWritingDirectRequest(BaseModel):
    """Request body for the manual '+' writing trigger (Work Item D).

    Binary mode choice only (no free-text topic input exists anywhere in
    the writing backend) -- mirrors WritingPage's existing mini-vs-weekly
    split.
    """

    writing_mode: str = Field(pattern="^(mini|weekly)$")


class SaveNoteRequest(BaseModel):
    """Request body for the manual '+' note trigger (Work Item E).

    Direct entry point into the same save_note_action code path
    the LLM tool-call already uses -- invoked directly instead of via
    a model decision, so this does NOT go through the LLM at all.
    """

    content: str = Field(min_length=1)


def _attachments_response(message_id: int) -> list[AttachmentResponse] | None:
    """Build the AttachmentResponse list for a message, or None if empty.

    Args:
        message_id: The message ID

    Returns:
        List of AttachmentResponse, or None if the message has no attachments
    """
    attachments = ChatService.list_attachments(message_id)
    if not attachments:
        return None
    return [
        AttachmentResponse(
            id=a.id, # type: ignore
            filename=a.filename,
            kind=a.kind.value,
            mime_type=a.mime_type,
            context_truncated=(
                a.kind == AttachmentKind.TEXT
                and bool(a.extracted_text)
                and len(a.extracted_text) > MAX_ATTACHMENT_CONTEXT_CHARS
            ),
        )
        for a in attachments
    ]


@router.post("/threads", response_model=ChatThreadResponse, status_code=201)
async def create_thread() -> ChatThreadResponse:
    """Create a new chat thread.

    Returns:
        ChatThreadResponse with the new thread
    """
    try:
        thread = ChatService.create_thread()
        return ChatThreadResponse(
            id=thread.id, # type: ignore
            title=thread.title,
            last_message_preview=thread.last_message_preview,
            updated_at=thread.updated_at,
        )
    except Exception as e:
        logger.error(f"Failed to create thread: {e}")
        raise HTTPException(status_code=500, detail="Failed to create thread")


@router.get("/threads", response_model=list[ChatThreadResponse])
async def list_threads(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[ChatThreadResponse]:
    """List chat threads ordered by updated_at descending.

    Args:
        limit: Maximum number of threads to return
        offset: Number of threads to skip

    Returns:
        List of ChatThreadResponse
    """
    try:
        threads = ChatService.list_threads(limit=limit, offset=offset)
        return [
            ChatThreadResponse(
                id=t.id, # type: ignore
                title=t.title,
                last_message_preview=t.last_message_preview,
                updated_at=t.updated_at,
            )
            for t in threads
        ]
    except Exception as e:
        logger.error(f"Failed to list threads: {e}")
        raise HTTPException(status_code=500, detail="Failed to list threads")


@router.get("/threads/{thread_id}", response_model=ChatThreadDetailResponse)
async def get_thread(thread_id: int) -> ChatThreadDetailResponse:
    """Get a chat thread with all its messages.

    Args:
        thread_id: The thread ID

    Returns:
        ChatThreadDetailResponse with thread and messages

    Raises:
        HTTPException: 404 if thread not found
    """
    try:
        thread = ChatService.get_thread(thread_id)
        messages = ChatService.list_messages(thread_id)

        return ChatThreadDetailResponse(
            id=thread.id, # type: ignore
            title=thread.title,
            created_at=thread.created_at,
            updated_at=thread.updated_at,
            last_message_preview=thread.last_message_preview,
            messages=[
                ChatMessageResponse(
                    id=m.id, # type: ignore
                    thread_id=m.thread_id,
                    role=m.role.value,
                    content=m.content,
                    action_type=m.action_type.value,
                    action_ref_id=m.action_ref_id,
                    created_at=m.created_at,
                    attachments=_attachments_response(m.id), # type: ignore
                )
                for m in messages
            ],
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get thread {thread_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get thread")


@router.delete("/threads/{thread_id}", status_code=204)
async def delete_thread(thread_id: int) -> None:
    """Delete a chat thread and all its messages.

    Args:
        thread_id: The thread ID

    Raises:
        HTTPException: 404 if thread not found
    """
    try:
        ChatService.delete_thread(thread_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete thread {thread_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete thread")


@router.post("/threads/{thread_id}/messages", response_model=SendMessageResponse)
async def send_message(
    thread_id: int,
    content: str = Form(...),
    files: list[UploadFile] = File(default=[]),
) -> SendMessageResponse:
    """Send a message in a thread and get a coach reply.

    This endpoint:
    1. Appends the user message
    2. Validates and processes any attached files (Epic B -- ephemeral,
       single-turn context; never fed into the vault-watcher/ingestion
       pipeline)
    3. Calls generate_reply to get the coach's response
    4. Returns both messages

    Args:
        thread_id: The thread ID
        content: Message content (multipart form field)
        files: Optional attached files (.txt, .md, .pdf, .docx, images)

    Returns:
        SendMessageResponse with user and assistant messages

    Raises:
        HTTPException: 404 if thread not found, 400 for unsupported/oversized
            attachments
    """
    try:
        # Verify thread exists
        ChatService.get_thread(thread_id)

        # Append user message
        user_message = ChatService.append_message(
            thread_id=thread_id,
            role=ChatRole.USER,
            content=content,
        )

        # Validate, extract, and persist any attachments (400s raised by
        # process_attachment propagate as-is, not caught by the except
        # blocks below).
        for upload in files:
            kind, extracted_text, stored_path = await process_attachment(upload)
            ChatService.add_attachment(
                message_id=user_message.id, # type: ignore
                filename=upload.filename or "attachment",
                mime_type=upload.content_type or "application/octet-stream",
                kind=kind,
                extracted_text=extracted_text,
                stored_path=stored_path,
            )

        # Generate assistant reply
        assistant_message = await ChatService.generate_reply(thread_id)

        return SendMessageResponse(
            user_message=ChatMessageResponse(
                id=user_message.id, # type: ignore
                thread_id=user_message.thread_id,
                role=user_message.role.value,
                content=user_message.content,
                action_type=user_message.action_type.value,
                action_ref_id=user_message.action_ref_id,
                created_at=user_message.created_at,
                attachments=_attachments_response(user_message.id), # type: ignore
            ),
            assistant_message=ChatMessageResponse(
                id=assistant_message.id, # type: ignore
                thread_id=assistant_message.thread_id,
                role=assistant_message.role.value,
                content=assistant_message.content,
                action_type=assistant_message.action_type.value,
                action_ref_id=assistant_message.action_ref_id,
                created_at=assistant_message.created_at,
            ),
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        reraise_known_ollama_error(e)
        logger.error(f"Failed to send message to thread {thread_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to send message")


@router.put("/threads/{thread_id}/messages/{message_id}", response_model=SendMessageResponse)
async def edit_message(
    thread_id: int, message_id: int, request: EditMessageRequest
) -> SendMessageResponse:
    """Edit a user message and regenerate the coach's reply (Epic A).

    This is a hard truncate-and-regenerate, not branching: editing a user
    message updates its content, deletes every later message in the thread,
    then generates a fresh assistant reply exactly as `send_message` does.

    Args:
        thread_id: The thread ID
        message_id: The message ID (must belong to the thread and be USER)
        request: New message content

    Returns:
        SendMessageResponse with the updated user message and new assistant message

    Raises:
        HTTPException: 404 if the thread or message isn't found, 400 if the
            message isn't a user message
    """
    try:
        # Verify thread and message exist and are related
        ChatService.get_thread(thread_id)
        message = ChatService.get_message(thread_id, message_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if message.role != ChatRole.USER:
        raise HTTPException(
            status_code=400, detail="Only user messages can be edited"
        )

    try:
        user_message = ChatService.update_message_content(
            thread_id, message_id, request.content
        )
        ChatService.truncate_after(thread_id, message_id)

        # Generate assistant reply
        assistant_message = await ChatService.generate_reply(thread_id)

        return SendMessageResponse(
            user_message=ChatMessageResponse(
                id=user_message.id, # type: ignore
                thread_id=user_message.thread_id,
                role=user_message.role.value,
                content=user_message.content,
                action_type=user_message.action_type.value,
                action_ref_id=user_message.action_ref_id,
                created_at=user_message.created_at,
            ),
            assistant_message=ChatMessageResponse(
                id=assistant_message.id, # type: ignore
                thread_id=assistant_message.thread_id,
                role=assistant_message.role.value,
                content=assistant_message.content,
                action_type=assistant_message.action_type.value,
                action_ref_id=assistant_message.action_ref_id,
                created_at=assistant_message.created_at,
            ),
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        reraise_known_ollama_error(e)
        logger.error(f"Failed to edit message {message_id} in thread {thread_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to edit message")


@router.get("/attachments/{attachment_id}/file")
async def get_attachment_file(attachment_id: int) -> FileResponse:
    """Serve a stored image attachment back for re-rendering (Epic B).

    Args:
        attachment_id: The attachment ID

    Returns:
        The stored file, with the attachment's original content-type and
        filename

    Raises:
        HTTPException: 404 if the attachment or its stored file is missing
    """
    try:
        attachment = ChatService.get_attachment(attachment_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if not attachment.stored_path or not Path(attachment.stored_path).exists():
        raise HTTPException(status_code=404, detail="Attachment file not found")

    return FileResponse(
        attachment.stored_path,
        media_type=attachment.mime_type,
        filename=attachment.filename,
    )


@router.post(
    "/threads/{thread_id}/quiz",
    response_model=ChatMessageResponse,
)
async def start_quiz_direct(
    thread_id: int, request: StartQuizDirectRequest
) -> ChatMessageResponse:
    """Start a quiz directly from the composer's '+' menu (Work Item D).

    A second entry point into the exact same start_quiz_action code path
    the LLM tool-call already uses -- invoked directly instead of via a
    model decision, so this does NOT go through the LLM at all.

    Args:
        thread_id: The thread ID
        request: Quiz size

    Returns:
        ChatMessageResponse with action_type=QUIZ and action_ref_id set

    Raises:
        HTTPException: 404 if thread not found
    """
    try:
        # Verify thread exists
        ChatService.get_thread(thread_id)

        message = await ChatService.start_quiz_action(
            thread_id, request.size
        )
        return ChatMessageResponse(
            id=message.id, # type: ignore
            thread_id=message.thread_id,
            role=message.role.value,
            content=message.content,
            action_type=message.action_type.value,
            action_ref_id=message.action_ref_id,
            created_at=message.created_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to start quiz directly for thread {thread_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to start quiz")


@router.post(
    "/threads/{thread_id}/writing",
    response_model=ChatMessageResponse,
)
async def start_writing_direct(
    thread_id: int, request: StartWritingDirectRequest
) -> ChatMessageResponse:
    """Start a writing session directly from the composer's '+' menu (Work Item D).

    A second entry point into the exact same start_writing_action code path
    the LLM tool-call already uses -- invoked directly instead of via a
    model decision, so this does NOT go through the LLM at all. Unlike the
    LLM tool-call path (which always uses "mini" with a free-text topic),
    this can also trigger "weekly" (auto-generated-topic) prompts.

    Args:
        thread_id: The thread ID
        request: Writing mode ("mini" or "weekly")

    Returns:
        ChatMessageResponse with action_type=WRITING and action_ref_id set

    Raises:
        HTTPException: 404 if thread not found
    """
    try:
        # Verify thread exists
        ChatService.get_thread(thread_id)

        message = await ChatService.start_writing_action(
            thread_id, writing_mode=request.writing_mode
        )
        return ChatMessageResponse(
            id=message.id, # type: ignore
            thread_id=message.thread_id,
            role=message.role.value,
            content=message.content,
            action_type=message.action_type.value,
            action_ref_id=message.action_ref_id,
            created_at=message.created_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to start writing directly for thread {thread_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to start writing")


@router.post(
    "/threads/{thread_id}/notes",
    response_model=ChatMessageResponse,
)
async def save_note_direct(
    thread_id: int, request: SaveNoteRequest
) -> ChatMessageResponse:
    """Save a note directly from the composer's '+' menu (Work Item E).

    A second entry point into the exact same save_note_action code path
    the LLM tool-call already uses -- invoked directly instead of via a
    model decision, so this does NOT go through the LLM at all.

    Args:
        thread_id: The thread ID
        request: Note content

    Returns:
        ChatMessageResponse with the confirmation message

    Raises:
        HTTPException: 404 if thread not found
    """
    try:
        # Verify thread exists
        ChatService.get_thread(thread_id)

        message = await ChatService.save_note_action(
            thread_id, request.content
        )
        return ChatMessageResponse(
            id=message.id, # type: ignore
            thread_id=message.thread_id,
            role=message.role.value,
            content=message.content,
            action_type=message.action_type.value,
            action_ref_id=message.action_ref_id,
            created_at=message.created_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to save note directly for thread {thread_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to save note")


@router.post(
    "/threads/{thread_id}/quiz/{session_id}/complete",
    response_model=ChatMessageResponse,
)
async def complete_quiz(thread_id: int, session_id: int) -> ChatMessageResponse:
    """Handle quiz completion and get a follow-up message.

    Called by the frontend after the inline quiz widget receives its graded
    summary from the existing quiz grading endpoint.

    Args:
        thread_id: The thread ID
        session_id: The quiz session ID

    Returns:
        ChatMessageResponse with the follow-up assistant message

    Raises:
        HTTPException: 404 if thread or session not found
    """
    try:
        message = await ChatService.on_quiz_graded(thread_id, session_id)
        return ChatMessageResponse(
            id=message.id, # type: ignore
            thread_id=message.thread_id,
            role=message.role.value,
            content=message.content,
            action_type=message.action_type.value,
            action_ref_id=message.action_ref_id,
            created_at=message.created_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        reraise_known_ollama_error(e)
        logger.error(f"Failed to complete quiz for thread {thread_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to complete quiz")


@router.post(
    "/threads/{thread_id}/writing/{prompt_id}/complete",
    response_model=ChatMessageResponse,
)
async def complete_writing(
    thread_id: int, prompt_id: int
) -> ChatMessageResponse:
    """Handle writing prompt completion and get a follow-up message.

    Args:
        thread_id: The thread ID
        prompt_id: The writing prompt ID

    Returns:
        ChatMessageResponse with the follow-up assistant message

    Raises:
        HTTPException: 404 if thread or prompt not found
    """
    try:
        message = await ChatService.on_writing_graded(thread_id, prompt_id)
        return ChatMessageResponse(
            id=message.id, # type: ignore
            thread_id=message.thread_id,
            role=message.role.value,
            content=message.content,
            action_type=message.action_type.value,
            action_ref_id=message.action_ref_id,
            created_at=message.created_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        reraise_known_ollama_error(e)
        logger.error(f"Failed to complete writing for thread {thread_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to complete writing")
