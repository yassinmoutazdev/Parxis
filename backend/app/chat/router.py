"""Chat API router.

Corresponds to PRAXIS_CHAT_COACH_PLAN Section 3.4 (first four endpoints) and Section 4.3 (remaining endpoints).
"""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query 
from pydantic import BaseModel, Field

from app.chat.service import ChatService
from app.db.models.chat import ChatActionType, ChatMessage, ChatRole, ChatThread
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatThreadResponse(BaseModel):
    """Response for a chat thread (list/detail view)."""

    id: int
    title: str | None
    last_message_preview: str | None
    updated_at: datetime


class ChatMessageResponse(BaseModel):
    """Response for a chat message."""

    id: int
    thread_id: int
    role: str
    content: str
    action_type: str
    action_ref_id: int | None
    created_at: datetime


class ChatThreadDetailResponse(BaseModel):
    """Response for a chat thread with its messages."""

    id: int
    title: str | None
    created_at: datetime
    updated_at: datetime
    last_message_preview: str | None
    messages: list[ChatMessageResponse]


class SendMessageRequest(BaseModel):
    """Request body for sending a message."""

    content: str


class SendMessageResponse(BaseModel):
    """Response for sending a message (returns both user and assistant messages)."""

    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse


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
    thread_id: int, request: SendMessageRequest
) -> SendMessageResponse:
    """Send a message in a thread and get a coach reply.

    This endpoint:
    1. Appends the user message
    2. Calls generate_reply to get the coach's response
    3. Returns both messages

    Args:
        thread_id: The thread ID
        request: Message content

    Returns:
        SendMessageResponse with user and assistant messages

    Raises:
        HTTPException: 404 if thread not found
    """
    try:
        # Verify thread exists
        ChatService.get_thread(thread_id)

        # Append user message
        user_message = ChatService.append_message(
            thread_id=thread_id,
            role=ChatRole.USER,
            content=request.content,
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
        logger.error(f"Failed to send message to thread {thread_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to send message")


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
        logger.error(f"Failed to complete writing for thread {thread_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to complete writing")
