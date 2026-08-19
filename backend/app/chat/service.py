"""Chat Service for managing chat threads and messages.

Corresponds to PRAXIS_CHAT_COACH_PLAN Section 3.3 (CRUD layer) and Section 4.2 (LLM integration).
"""

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, or_

from app.chat.attachments import MAX_ATTACHMENT_CONTEXT_CHARS, read_image_base64
from app.db.engine import Session
from app.db.models.chat import (
    AttachmentKind,
    ChatActionType,
    ChatMessage,
    ChatMessageAttachment,
    ChatRole,
    ChatThread,
)
from app.db.models.learning_item import LearningItem
from app.db.models.note import Note, NoteSource, NoteStatus
from app.ingestion.service import IngestionService
from app.llm import ollama_adapter
from app.llm.interface import TaskType
from app.llm.prompts import coach as coach_prompts
from app.llm.schemas import CoachFollowupReply, CoachHistorySummary, CoachThreadTitle
from app.llm.tools import COACH_TOOLS
from app.quizzes.service import QuizService
from app.writing.service import WritingService


logger = logging.getLogger(__name__)

# Rough chars-per-token heuristic for English text. Ollama doesn't expose a
# tokenizer over the API, so this is a soft, approximate budget -- not an
# exact count. May undercount non-English text; acceptable for an internal
# soft budget.
_CHARS_PER_TOKEN_ESTIMATE = 4


def _estimate_tokens(text: str) -> int:
    """Roughly estimate the token count of a string via a chars-per-token
    heuristic. Approximate only -- good enough for a soft internal budget.
    """
    return max(1, len(text) // _CHARS_PER_TOKEN_ESTIMATE)


# Token budget for system prompt + rolling summary + raw (unsummarized)
# messages combined, for the main chat loop. The configured model has a
# large nominal context window, but (a) long-context models lose recall
# reliability well before their hard limit ("lost in the middle"), and
# (b) every turn re-sends the entire history, so an unbounded history means
# every subsequent reply pays that cost repeatedly. This is a plain
# constant, not user-configurable, intended to be tuned later once real
# usage is observed.
CHAT_HISTORY_TOKEN_BUDGET = 12_000  # tokens


class ChatService:
    """Service for chat thread and message CRUD operations.

    Handles creation, retrieval, listing, and deletion of chat threads
    and their messages.
    """

    @classmethod
    def create_thread(cls) -> ChatThread:
        """Create a new empty chat thread.

        Returns:
            A new ChatThread with title=None
        """
        with Session() as session:
            thread = ChatThread(
                title=None,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                last_message_preview=None,
            )
            session.add(thread)
            session.commit()
            session.refresh(thread)
            return thread

    @classmethod
    def list_threads(
        cls, limit: int = 50, offset: int = 0
    ) -> list[ChatThread]:
        """List chat threads ordered by updated_at descending.

        Args:
            limit: Maximum number of threads to return
            offset: Number of threads to skip

        Returns:
            List of ChatThread objects
        """
        with Session() as session:
            threads = (
                session.query(ChatThread)
                .order_by(ChatThread.updated_at.desc())  # type: ignore[union-attr]
                .offset(offset)
                .limit(limit)
                .all()
            )
            return threads

    @classmethod
    def get_thread(cls, thread_id: int) -> ChatThread:
        """Get a chat thread by ID.

        Args:
            thread_id: The thread ID

        Returns:
            The ChatThread

        Raises:
            ValueError: If thread not found
        """
        with Session() as session:
            thread = session.get(ChatThread, thread_id)
            if not thread:
                raise ValueError(f"Chat thread {thread_id} not found")
            return thread

    @classmethod
    def list_messages(cls, thread_id: int) -> list[ChatMessage]:
        """List messages in a thread ordered by created_at ascending.

        Args:
            thread_id: The thread ID

        Returns:
            List of ChatMessage objects
        """
        with Session() as session:
            messages = (
                session.query(ChatMessage)
                .filter(ChatMessage.thread_id == thread_id)  # type: ignore
                .order_by(ChatMessage.created_at.asc())  # type: ignore
                .all()
            )
            return messages

    @classmethod
    def list_attachments(cls, message_id: int) -> list[ChatMessageAttachment]:
        """List attachments for a message, ordered by creation.

        Args:
            message_id: The message ID

        Returns:
            List of ChatMessageAttachment objects
        """
        with Session() as session:
            return (
                session.query(ChatMessageAttachment)
                .filter(ChatMessageAttachment.message_id == message_id)  # type: ignore
                .order_by(ChatMessageAttachment.created_at.asc())  # type: ignore
                .all()
            )

    @classmethod
    def get_attachment(cls, attachment_id: int) -> ChatMessageAttachment:
        """Get an attachment by ID.

        Args:
            attachment_id: The attachment ID

        Returns:
            The ChatMessageAttachment

        Raises:
            ValueError: If not found
        """
        with Session() as session:
            attachment = session.get(ChatMessageAttachment, attachment_id)
            if not attachment:
                raise ValueError(f"Chat attachment {attachment_id} not found")
            return attachment

    @classmethod
    def add_attachment(
        cls,
        message_id: int,
        filename: str,
        mime_type: str,
        kind: AttachmentKind,
        extracted_text: str | None = None,
        stored_path: str | None = None,
    ) -> ChatMessageAttachment:
        """Persist a single chat message attachment row.

        Ephemeral, single-turn context only (Epic B): this only ever
        attaches to a ChatMessage -- it never touches the vault-watcher/
        ingestion pipeline and never creates learning_item/
        learning_correction/note records.

        Args:
            message_id: The message this attachment belongs to
            filename: Original filename
            mime_type: The upload's content type
            kind: TEXT or IMAGE
            extracted_text: Extracted text, for TEXT-kind attachments
            stored_path: Path to the saved file, for IMAGE-kind attachments

        Returns:
            The created ChatMessageAttachment
        """
        with Session() as session:
            attachment = ChatMessageAttachment(
                message_id=message_id,
                filename=filename,
                mime_type=mime_type,
                kind=kind,
                extracted_text=extracted_text,
                stored_path=stored_path,
                created_at=datetime.now(timezone.utc),
            )
            session.add(attachment)
            session.commit()
            session.refresh(attachment)
            return attachment

    @classmethod
    def append_message(
        cls,
        thread_id: int,
        role: ChatRole,
        content: str,
        action_type: ChatActionType = ChatActionType.NONE,
        action_ref_id: int | None = None,
    ) -> ChatMessage:
        """Append a message to a thread and update thread metadata.

        Args:
            thread_id: The thread ID
            role: The message role (USER or ASSISTANT)
            content: The message content
            action_type: The action type (NONE, QUIZ, WRITING)
            action_ref_id: Reference ID for the action (quiz_session_id or writing_submission_id)

        Returns:
            The created ChatMessage
        """
        with Session() as session:
            # Verify thread exists
            thread = session.get(ChatThread, thread_id)
            if not thread:
                raise ValueError(f"Chat thread {thread_id} not found")

            # Create message
            message = ChatMessage(
                thread_id=thread_id,
                role=role,
                content=content,
                action_type=action_type,
                action_ref_id=action_ref_id,
                created_at=datetime.now(timezone.utc),
            )
            session.add(message)

            # Update thread metadata
            thread.updated_at = datetime.now(timezone.utc)
            # Truncate preview to ~120 chars
            thread.last_message_preview = content[:120] if content else None

            session.commit()
            session.refresh(message)
            return message

    @classmethod
    def get_message(cls, thread_id: int, message_id: int) -> ChatMessage:
        """Get a message by ID, scoped to a thread.

        Args:
            thread_id: The thread the message is expected to belong to
            message_id: The message ID

        Returns:
            The ChatMessage

        Raises:
            ValueError: If the message doesn't exist or belongs to a
                different thread
        """
        with Session() as session:
            message = session.get(ChatMessage, message_id)
            if not message or message.thread_id != thread_id:
                raise ValueError(
                    f"Chat message {message_id} not found in thread {thread_id}"
                )
            return message

    @classmethod
    def update_message_content(
        cls, thread_id: int, message_id: int, content: str
    ) -> ChatMessage:
        """Update a message's content in place.

        Args:
            thread_id: The thread the message is expected to belong to
            message_id: The message ID
            content: The new content

        Returns:
            The updated ChatMessage

        Raises:
            ValueError: If the message doesn't exist or belongs to a
                different thread
        """
        with Session() as session:
            message = session.get(ChatMessage, message_id)
            if not message or message.thread_id != thread_id:
                raise ValueError(
                    f"Chat message {message_id} not found in thread {thread_id}"
                )
            message.content = content
            session.commit()
            session.refresh(message)
            return message

    @classmethod
    def truncate_after(cls, thread_id: int, message_id: int) -> None:
        """Delete every message in a thread positioned after the given message.

        Position follows the same (created_at, id) ordering `list_messages`
        returns, so `created_at` ties are broken deterministically by id.
        Used by the edit-with-regenerate flow to hard-truncate a thread back
        to the edited message before a fresh reply is generated.

        Args:
            thread_id: The thread ID
            message_id: The anchor message; everything after it is deleted

        Raises:
            ValueError: If the anchor message doesn't exist or belongs to a
                different thread
        """
        with Session() as session:
            anchor = session.get(ChatMessage, message_id)
            if not anchor or anchor.thread_id != thread_id:
                raise ValueError(
                    f"Chat message {message_id} not found in thread {thread_id}"
                )
            truncate_condition = and_(
                ChatMessage.thread_id == thread_id,  # type: ignore
                or_(
                    ChatMessage.created_at > anchor.created_at,  # type: ignore
                    and_(
                        ChatMessage.created_at == anchor.created_at,  # type: ignore
                        ChatMessage.id > anchor.id,  # type: ignore
                    ),
                ),
            )

            message_ids = [
                row[0]
                for row in session.query(ChatMessage.id).filter(truncate_condition).all()
            ]

            # Same FK issue as delete_thread: clear attachments on the
            # messages being truncated before deleting the messages
            # themselves, or this raises IntegrityError as soon as one of
            # them has an attachment.
            if message_ids:
                session.query(ChatMessageAttachment).filter(
                    ChatMessageAttachment.message_id.in_(message_ids)  # type: ignore
                ).delete(synchronize_session=False)

            session.query(ChatMessage).filter(truncate_condition).delete(
                synchronize_session=False
            )
            session.commit()

    @classmethod
    def delete_thread(cls, thread_id: int) -> None:
        """Delete a chat thread and all its messages.

        Args:
            thread_id: The thread ID

        Raises:
            ValueError: If thread not found
        """
        with Session() as session:
            thread = session.get(ChatThread, thread_id)
            if not thread:
                raise ValueError(f"Chat thread {thread_id} not found")

            message_ids = [
                row[0]
                for row in session.query(ChatMessage.id)
                .filter(ChatMessage.thread_id == thread_id)  # type: ignore
                .all()
            ]

            # ChatMessageAttachment FK-references chat_message.id with no
            # ON DELETE CASCADE, and PRAGMA foreign_keys=ON is set - so any
            # attachments on these messages must be cleared first, or the
            # bulk delete below raises sqlite3.IntegrityError (this was the
            # actual cause of "delete a thread" 500s once a message in it
            # had an attachment).
            if message_ids:
                session.query(ChatMessageAttachment).filter(
                    ChatMessageAttachment.message_id.in_(message_ids)  # type: ignore
                ).delete(synchronize_session=False)

            # Delete messages first (cascade would handle this but be explicit)
            session.query(ChatMessage).filter(ChatMessage.thread_id == thread_id).delete()  # type: ignore

            # Delete thread
            session.delete(thread)
            session.commit()

    # =========================================================================
    # LLM Integration Methods (Section 4.2)
    # =========================================================================

    @classmethod
    def _format_writing_feedback(cls, feedback_json: dict) -> str:
        """Format a WritingEvaluation.feedback_json dict into readable text.

        Handles both shapes WritingService produces: mini evaluations
        ({"corrections": [...], "naturalness_notes": [...]}) and weekly
        evaluations ({"grammar": str, "naturalness": str, ...}), plus the
        failed-evaluation shape ({"error": str}).

        Args:
            feedback_json: The evaluation's stored feedback_json dict

        Returns:
            Human-readable feedback text for the coach prompt context
        """
        if not feedback_json:
            return "No feedback available."

        if "error" in feedback_json:
            return "Evaluation failed to complete."

        if "corrections" in feedback_json:
            # Mini evaluation shape
            lines = []
            for c in feedback_json.get("corrections", []):
                lines.append(
                    f"- \"{c.get('wrong')}\" should be \"{c.get('correct')}\" "
                    f"({c.get('explanation')})"
                )
            for note in feedback_json.get("naturalness_notes", []):
                lines.append(f"- {note}")
            return "\n".join(lines) if lines else "No corrections - well done."

        # Weekly evaluation shape: one feedback string per dimension
        dimension_order = ["grammar", "naturalness", "vocabulary", "coherence", "overall"]
        lines = [
            f"- {dim.capitalize()}: {feedback_json[dim]}"
            for dim in dimension_order
            if feedback_json.get(dim)
        ]
        return "\n".join(lines) if lines else "No feedback available."

    @classmethod
    def _format_messages(cls, messages: list[ChatMessage]) -> str:
        """Format messages for the JSON-schema-based follow-up prompts.

        Args:
            messages: List of ChatMessage objects

        Returns:
            Formatted string of messages
        """
        lines = []
        for msg in messages[-20:]:  # Last 20 messages
            role = msg.role.value
            lines.append(f"{role}: {msg.content}")
        return "\n".join(lines)

    @classmethod
    def _format_history_for_tools(
        cls, messages: list[ChatMessage]
    ) -> list[dict[str, Any]]:
        """Format messages as a chat history list for tool-calling turns.

        Unlike `_format_messages` (a single flattened string for the old
        JSON-schema prompts), this keeps each turn as its own message dict so
        the model sees a proper multi-turn chat, per Ollama's native chat
        message format.

        Epic B: any attachments on a message are folded into that same
        turn -- text/markdown/PDF/DOCX extracted text is appended to the
        message content (clearly delimited), and image bytes are collected
        into that message dict's `images` field per Ollama's native
        multimodal chat API.

        Args:
            messages: List of ChatMessage objects to include -- the caller
                is responsible for selecting which messages to pass in (e.g.
                the "raw", not-yet-summarized tail of the thread); this
                method no longer applies its own count-based cap.

        Returns:
            List of {"role": "user"|"assistant", "content": str, "images"?:
            list[str]} dicts, SYSTEM-role messages excluded (the system
            prompt is sent separately).
        """
        role_map = {ChatRole.USER: "user", ChatRole.ASSISTANT: "assistant"}
        history: list[dict[str, Any]] = []
        for msg in messages:
            mapped_role = role_map.get(msg.role)
            if mapped_role is None:
                continue

            content = msg.content
            images: list[str] = []

            for attachment in cls.list_attachments(msg.id) if msg.id else []:
                if attachment.kind == AttachmentKind.TEXT and attachment.extracted_text:
                    text = attachment.extracted_text
                    if len(text) > MAX_ATTACHMENT_CONTEXT_CHARS:
                        text = (
                            text[:MAX_ATTACHMENT_CONTEXT_CHARS]
                            + "\n[... truncated, file was longer than this ...]"
                        )
                    content += f"\n\n[Attached: {attachment.filename}]\n{text}"
                elif attachment.kind == AttachmentKind.IMAGE and attachment.stored_path:
                    images.append(read_image_base64(attachment.stored_path))

            entry: dict[str, Any] = {"role": mapped_role, "content": content}
            if images:
                entry["images"] = images
            history.append(entry)
        return history

    @classmethod
    async def generate_reply(cls, thread_id: int) -> ChatMessage:
        """Generate an assistant reply for a thread.

        This is the core orchestration method that:
        1. Loads thread history
        2. Calls the LLM with the coach prompt
        3. Persists the assistant's reply
        4. Updates thread title if needed
        5. Handles any action (quiz/writing) if triggered

        Args:
            thread_id: The thread ID

        Returns:
            The persisted ChatMessage with action_type/action_ref_id populated if applicable
        """
        # Load thread and messages
        thread = cls.get_thread(thread_id)
        messages = cls.list_messages(thread_id)

        # Token-budget-based rolling summary: fold enough of the oldest
        # unsummarized messages into thread.history_summary (if needed) so
        # that the raw remainder fits under CHAT_HISTORY_TOKEN_BUDGET, then
        # build the system prompt + per-turn chat history from just that
        # raw remainder.
        summary = await cls._maybe_update_summary(thread, messages)
        summarized_up_to = thread.summarized_up_to_message_id or 0
        raw_messages = [m for m in messages if m.id > summarized_up_to]

        system_prompt = coach_prompts.COACH_CHAT_SYSTEM_PROMPT
        if summary:
            system_prompt += (
                f"\n\nSummary of earlier parts of this conversation:\n{summary}"
            )

        history = cls._format_history_for_tools(raw_messages)

        # Check if this is the first assistant reply (for title suggestion)
        is_first_reply = not any(m.role == ChatRole.ASSISTANT for m in messages)

        try:
            # Call the LLM with real tool-calling (no forced JSON `action`)
            result = await ollama_adapter.ollama_adapter.generate_chat_with_tools(
                task=TaskType.COACH_CHAT,
                system_prompt=system_prompt,
                history=history,
                tools=COACH_TOOLS,
            )

            assistant_message: ChatMessage

            if result.tool_name == "start_quiz":
                args = result.tool_arguments or {}
                quiz_size = args.get("quiz_size") or 10

                # Tool call ends the turn: a short client-side confirmation
                # is enough, no extra LLM round-trip (per ADR).
                assistant_message = await cls.start_quiz_action(
                    thread_id, quiz_size
                )

            elif result.tool_name == "start_writing":
                args = result.tool_arguments or {}
                topic = args.get("writing_topic") or "Free writing"
                assistant_message = await cls.start_writing_action(
                    thread_id, writing_mode="mini", topic=topic
                )

            elif result.tool_name == "save_note":
                args = result.tool_arguments or {}
                content = args.get("content") or ""
                assistant_message = await cls.save_note_action(
                    thread_id, content
                )

            else:
                # Ordinary conversational turn -- plain text, no action.
                assistant_message = cls.append_message(
                    thread_id=thread_id,
                    role=ChatRole.ASSISTANT,
                    content=result.content,
                    action_type=ChatActionType.NONE,
                    action_ref_id=None,
                )

            # Generate a thread title via a separate lightweight LLM call,
            # only for the first assistant reply in a new thread.
            if is_first_reply and thread.title is None:
                await cls._maybe_set_thread_title(
                    thread_id=thread_id,
                    user_message=messages[-1].content if messages else "",
                    assistant_reply=assistant_message.content,
                )

            return assistant_message

        except Exception as e:
            logger.error(f"Failed to generate reply for thread {thread_id}: {e}")
            # If LLM fails, append a fallback message
            return cls.append_message(
                thread_id=thread_id,
                role=ChatRole.ASSISTANT,
                content="I'm sorry, I encountered an error. Please try again.",
            )

    @classmethod
    async def _maybe_update_summary(
        cls, thread: ChatThread, messages: list[ChatMessage]
    ) -> str | None:
        """Ensure thread.history_summary covers enough of the older history
        to keep the *raw* (unsummarized) remainder under the token budget.

        Best-effort: on any LLM failure, logs and returns the existing
        (possibly stale) summary rather than raising -- this must never
        block the actual chat reply.

        Args:
            thread: The thread (mutated in place on success, so the
                caller's copy of summarized_up_to_message_id / history_summary
                stays in sync with what was just persisted)
            messages: All messages in the thread, oldest first

        Returns:
            The current (possibly just-updated) history_summary, or None if
            the thread has never needed one.
        """
        summary = thread.history_summary
        summarized_up_to = thread.summarized_up_to_message_id or 0
        unsummarized = [m for m in messages if m.id > summarized_up_to]

        def _tokens_for(msgs: list[ChatMessage]) -> int:
            text = coach_prompts.COACH_CHAT_SYSTEM_PROMPT + (summary or "")
            for m in msgs:
                text += m.content
                for att in cls.list_attachments(m.id) if m.id else []:
                    if att.kind == AttachmentKind.TEXT and att.extracted_text:
                        text += att.extracted_text[:MAX_ATTACHMENT_CONTEXT_CHARS]
            return _estimate_tokens(text)

        if _tokens_for(unsummarized) <= CHAT_HISTORY_TOKEN_BUDGET:
            return summary  # nothing to do this turn

        # Fold the oldest unsummarized messages into the summary until the
        # remainder fits -- always leave at least the single newest message
        # raw, so there's guaranteed forward progress even if one message
        # alone (e.g. a huge attachment) exceeds the budget by itself.
        to_fold: list[ChatMessage] = []
        remaining = list(unsummarized)
        while len(remaining) > 1 and _tokens_for(remaining) > CHAT_HISTORY_TOKEN_BUDGET:
            to_fold.append(remaining.pop(0))

        if not to_fold:
            # A single message alone exceeds the budget -- nothing safe to
            # fold without losing all context. Send as-is; can't do better.
            return summary

        try:
            result = await ollama_adapter.ollama_adapter.generate(
                task=TaskType.COACH_CHAT_SUMMARIZE,
                context={
                    "previous_summary": summary or "(no summary yet)",
                    "messages": cls._format_messages(to_fold),
                },
                output_schema=CoachHistorySummary,
            )
            new_summary = result.summary  # type: ignore[attr-defined]
        except Exception as e:
            logger.warning(f"Summarization failed for thread {thread.id}: {e}")
            return summary

        with Session() as session:
            t = session.get(ChatThread, thread.id)
            if t:
                t.history_summary = new_summary
                t.summarized_up_to_message_id = to_fold[-1].id
                session.commit()

        # Keep the caller's in-memory thread object in sync with what was
        # just persisted, so downstream logic in generate_reply (which
        # reads thread.summarized_up_to_message_id from this same object)
        # sees the update without needing a re-fetch.
        thread.history_summary = new_summary
        thread.summarized_up_to_message_id = to_fold[-1].id

        return new_summary

    @classmethod
    async def _maybe_set_thread_title(
        cls, thread_id: int, user_message: str, assistant_reply: str
    ) -> None:
        """Generate and persist a short thread title via a small LLM call.

        Best-effort: title generation failures are logged and swallowed so
        they never block the actual chat reply from being returned.

        Args:
            thread_id: The thread ID
            user_message: The learner's first message in the thread
            assistant_reply: The coach's first reply
        """
        try:
            title_result = await ollama_adapter.ollama_adapter.generate(
                task=TaskType.COACH_THREAD_TITLE,
                context={
                    "user_message": user_message,
                    "assistant_reply": assistant_reply,
                },
                output_schema=CoachThreadTitle,
            )
            with Session() as session:
                thread_obj = session.get(ChatThread, thread_id)
                if thread_obj and thread_obj.title is None and title_result.title:  # type: ignore
                    thread_obj.title = title_result.title.strip()  # type: ignore
                    session.commit()
        except Exception as e:
            logger.warning(f"Failed to generate thread title for thread {thread_id}: {e}")

    @classmethod
    async def start_quiz_action(
        cls, thread_id: int, size: int
    ) -> ChatMessage:
        """Start a quiz action in a thread.

        Calls the existing QuizService.start_session, then appends a message
        with action_type=QUIZ and action_ref_id=session.id.

        Args:
            thread_id: The thread ID
            size: Number of questions

        Returns:
            ChatMessage with action_type=QUIZ and action_ref_id set
        """
        # Start the quiz session
        session, _ = await QuizService.start_session(
            size=size,
        )

        # Append message with action reference
        message = cls.append_message(
            thread_id=thread_id,
            role=ChatRole.ASSISTANT,
            content="Quiz started.",
            action_type=ChatActionType.QUIZ,
            action_ref_id=session.id,
        )

        return message

    @classmethod
    async def start_writing_action(
        cls, thread_id: int, writing_mode: str = "mini", topic: str | None = None
    ) -> ChatMessage:
        """Start a writing action in a thread.

        Mode-aware: "mini" generates a mini prompt (optionally overriding its
        topic, used by the LLM tool-call path which supplies a free-text
        topic); "weekly" generates a real auto-generated-topic prompt via
        WritingService.generate_weekly_prompt() instead of hijacking a mini
        prompt's topic field, which is what this previously did
        unconditionally (see Bug 3 / Work Item D).

        Appends a message with action_type=WRITING and action_ref_id=prompt.id.

        Args:
            thread_id: The thread ID
            writing_mode: "mini" or "weekly". Defaults to "mini" to match the
                LLM tool-call path's prior behavior.
            topic: Free-text topic override, only meaningful for "mini" (the
                LLM tool-call path supplies this; the manual "+" trigger does
                not, since there's no free-text topic input in the UI).

        Returns:
            ChatMessage with action_type=WRITING and action_ref_id set
        """
        if writing_mode == "weekly":
            prompt = await WritingService.generate_weekly_prompt()
            display_topic = prompt.topic
        else:
            prompt = WritingService.generate_mini_prompt()

            # Update the prompt topic if the caller supplied one (LLM
            # tool-call path only -- the manual "+" trigger never does).
            if topic:
                with Session() as session:
                    from app.db.models.writing import WritingPrompt as WritingPromptModel
                    p = session.get(WritingPromptModel, prompt.id)
                    if p:
                        p.topic = topic
                        session.commit()
            display_topic = topic or prompt.topic

        # Append message with action reference
        message = cls.append_message(
            thread_id=thread_id,
            role=ChatRole.ASSISTANT,
            content=f"Writing session started on: {display_topic}",
            action_type=ChatActionType.WRITING,
            action_ref_id=prompt.id,
        )

        return message

    @classmethod
    async def save_note_action(cls, thread_id: int, content: str) -> ChatMessage:
        """Save a note from chat content and process it through the ingestion pipeline.

        Creates a Note row with source=CHAT (its text lives inline in
        Note.content - there's no vault file), then processes it exactly
        like a vault note. No approval queue: items are auto-inserted,
        silently dropped as duplicates, or - if still low-confidence/
        incomplete after one automatic retry - handed back here so the
        coach can ask the user directly in this same reply.

        Args:
            thread_id: The thread ID
            content: The text content to save

        Returns:
            ChatMessage summarizing what happened (and asking for
            clarification, if anything needs it)
        """
        import hashlib

        with Session() as session:
            content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
            note = Note(
                source=NoteSource.CHAT,
                content=content,
                content_hash=content_hash,
                status=NoteStatus.NEW,
            )
            session.add(note)
            session.commit()
            session.refresh(note)
            note_id = note.id

        success, unresolved = IngestionService.process_note(note_id)

        if not success:
            reply = "I saved your note, but had trouble processing it - you can try again later."
        elif unresolved:
            # Bundle everything unresolved into one natural message, not one
            # interruption per item.
            questions = "; ".join(
                item.low_confidence_reason or f"could you clarify \"{item.text}\"?"
                for item in unresolved
            )
            reply = f"Got it, saved what I could. One thing I wasn't sure about: {questions}"
        else:
            reply = "Got it - I've added what's worth keeping from that to your learning set."

        return cls.append_message(
            thread_id=thread_id,
            role=ChatRole.ASSISTANT,
            content=reply,
        )

    @classmethod
    def _build_comprehensive_quiz_context(cls, thread_id: int, questions: list) -> dict:
        """Build rich context for comprehensive post-quiz feedback."""
        total = len(questions)
        correct = sum(1 for q in questions if q.is_correct is True)
        incorrect = total - correct
        score_pct = round(correct / total * 100) if total > 0 else 0

        # ALL questions with details - fetch learning items for item_type
        all_questions = []
        error_categories = {}

        with Session() as session:
            for i, q in enumerate(questions, 1):
                is_correct = q.is_correct is True
                item_type = "unknown"
                if q.learning_item_id:
                    item = session.get(LearningItem, q.learning_item_id)
                    if item:
                        item_type = item.item_type.value

                all_questions.append({
                    "number": i,
                    "type": q.question_type.value,
                    "prompt": q.prompt,
                    "user_answer": q.user_answer or "(no answer)",
                    "correct_answer": q.correct_answer or "(open-ended)",
                    "is_correct": is_correct,
                    "score": q.score,
                    "item_type": item_type,
                })

                if not is_correct:
                    error_categories[item_type] = error_categories.get(item_type, 0) + 1

        # Focus areas ranked
        focus_areas = sorted(error_categories.items(), key=lambda x: -x[1])

        # Get conversation history
        messages = cls.list_messages(thread_id)
        messages_text = cls._format_messages(messages[-20:])

        return {
            "total": total,
            "correct": correct,
            "incorrect": incorrect,
            "score_pct": score_pct,
            "all_questions": all_questions,
            "focus_areas": focus_areas,
            "messages": messages_text,
        }

    @classmethod
    def _format_all_questions(cls, questions: list[dict]) -> str:
        lines = []
        for q in questions:
            status = "✓" if q["is_correct"] else "✗"
            lines.append(
                f"{status} Q{q['number']} [{q['type']}] {q['prompt']}\n"
                f"   Your answer: {q['user_answer']}\n"
                f"   Correct: {q['correct_answer']}"
            )
        return "\n\n".join(lines)

    @classmethod
    def _format_focus_areas(cls, focus_areas: list[tuple]) -> str:
        if not focus_areas:
            return "None - great job!"
        return ", ".join(f"{cat} ({count})" for cat, count in focus_areas[:3])

    @classmethod
    async def on_quiz_graded(cls, thread_id: int, session_id: int) -> ChatMessage:
        """Handle quiz completion - generate comprehensive follow-up message.

        Called after the user submits quiz answers. Fetches the graded session
        summary and calls the LLM for a comprehensive follow-up message.

        Args:
            thread_id: The thread ID
            session_id: The quiz session ID

        Returns:
            ChatMessage with the follow-up assistant reply
        """
        # Get graded session
        _, questions = QuizService.get_session_with_questions(session_id)

        # Build comprehensive context
        ctx = cls._build_comprehensive_quiz_context(thread_id, questions)
        ctx["all_questions_formatted"] = cls._format_all_questions(ctx["all_questions"])
        ctx["focus_areas_formatted"] = cls._format_focus_areas(ctx["focus_areas"])

        try:
            # Call LLM for follow-up
            result = await ollama_adapter.ollama_adapter.generate(
                task=TaskType.COACH_CHAT_AFTER_QUIZ,
                context=ctx,
                output_schema=CoachFollowupReply,
            )

            # Persist follow-up message (no action)
            return cls.append_message(
                thread_id=thread_id,
                role=ChatRole.ASSISTANT,
                content=result.reply_text,  # type: ignore[attr-defined]
            )

        except Exception as e:
            logger.error(f"Failed to generate quiz follow-up for thread {thread_id}: {e}")
            correct = sum(1 for q in questions if q.is_correct is True)
            total = len(questions)
            return cls.append_message(
                thread_id=thread_id,
                role=ChatRole.ASSISTANT,
                content=f"Great job completing the quiz! You got {correct}/{total} correct.",
            )

    @classmethod
    async def on_writing_graded(
        cls, thread_id: int, prompt_id: int
    ) -> ChatMessage:
        """Handle writing prompt completion - generate follow-up message.

        Note: For the chat integration, we receive the prompt_id (not submission_id).
        The frontend handles the actual writing submission flow.

        Args:
            thread_id: The thread ID
            prompt_id: The writing prompt ID

        Returns:
            ChatMessage with the follow-up assistant reply
        """
        # Get the prompt
        from app.writing.service import WritingService

        prompt = WritingService.get_prompt(prompt_id)

        if not prompt:
            raise ValueError(f"Writing prompt {prompt_id} not found")

        # Pull the real submission/evaluation for this prompt instead of the
        # previous hardcoded placeholders, so the coach can reference actual
        # word count and evaluation feedback.
        result = WritingService.get_latest_submission_for_prompt(prompt_id)
        if result:
            submission, evaluation = result
            word_count = submission.word_count
            if evaluation and evaluation.feedback_json:
                feedback_points = cls._format_writing_feedback(evaluation.feedback_json)
            else:
                feedback_points = "Evaluation not yet available."
        else:
            word_count = 0
            feedback_points = "No submission recorded yet."

        # Get messages for context
        messages = cls.list_messages(thread_id)
        messages_text = cls._format_messages(messages)

        context = {
            "messages": messages_text,
            "topic": prompt.topic if prompt.topic else "Writing",
            "word_count": word_count,
            "feedback_points": feedback_points,
        }

        try:
            # Call LLM for follow-up
            result = await ollama_adapter.ollama_adapter.generate(
                task=TaskType.COACH_CHAT_AFTER_WRITING,
                context=context,
                output_schema=CoachFollowupReply,
            )

            # Persist follow-up message (no action)
            return cls.append_message(
                thread_id=thread_id,
                role=ChatRole.ASSISTANT,
                content=result.reply_text,  # type: ignore[attr-defined]
            )

        except Exception as e:
            logger.error(f"Failed to generate writing follow-up for thread {thread_id}: {e}")
            return cls.append_message(
                thread_id=thread_id,
                role=ChatRole.ASSISTANT,
                content="Great job completing your writing exercise!",
            )
