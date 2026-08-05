"""Chat Service for managing chat threads and messages.

Corresponds to PRAXIS_CHAT_COACH_PLAN Section 3.3 (CRUD layer) and Section 4.2 (LLM integration).
"""

import logging
from datetime import datetime
from typing import Any

from app.db.engine import Session
from app.db.models.chat import ChatActionType, ChatMessage, ChatRole, ChatThread
from app.db.models.learning_item import LearningItem
from app.db.models.quiz import QuizMode, QuizSession
from app.db.models.writing import WritingSubmission
from app.llm import ollama_adapter
from app.llm.interface import TaskType
from app.llm.prompts import coach as coach_prompts
from app.llm.schemas import CoachFollowupReply, CoachThreadTitle
from app.llm.tools import COACH_TOOLS
from app.quizzes.service import QuizService
from app.retrieval.service import RetrievalService, is_due
from app.scheduler.mastery import decayed_score
from app.writing.service import WritingService

logger = logging.getLogger(__name__)


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
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
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
                .order_by(ChatThread.updated_at.desc())
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
                .filter(ChatMessage.thread_id == thread_id)
                .order_by(ChatMessage.created_at.asc())
                .all()
            )
            return messages

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
                created_at=datetime.utcnow(),
            )
            session.add(message)

            # Update thread metadata
            thread.updated_at = datetime.utcnow()
            # Truncate preview to ~120 chars
            thread.last_message_preview = content[:120] if content else None

            session.commit()
            session.refresh(message)
            return message

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

            # Delete messages first (cascade would handle this but be explicit)
            session.query(ChatMessage).filter(ChatMessage.thread_id == thread_id).delete()

            # Delete thread
            session.delete(thread)
            session.commit()

    # =========================================================================
    # LLM Integration Methods (Section 4.2)
    # =========================================================================

    @classmethod
    def _get_learner_state(cls) -> dict[str, Any]:
        """Get compact summary of learner's current state for grounding.

        Returns:
            Dict with due_count and optionally weekly report summary
        """
        with Session() as session:
            # Count items due for review
            all_items = session.query(LearningItem).filter(
                LearningItem.suspended == False  # noqa: E712
            ).all()

            now = datetime.utcnow()
            due_count = sum(1 for item in all_items if is_due(item, now))

            return {"due_count": due_count}

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
    ) -> list[dict[str, str]]:
        """Format messages as a chat history list for tool-calling turns.

        Unlike `_format_messages` (a single flattened string for the old
        JSON-schema prompts), this keeps each turn as its own message dict so
        the model sees a proper multi-turn chat, per Ollama's native chat
        message format.

        Args:
            messages: List of ChatMessage objects

        Returns:
            List of {"role": "user"|"assistant", "content": str} dicts,
            SYSTEM-role messages excluded (the system prompt is sent
            separately).
        """
        role_map = {ChatRole.USER: "user", ChatRole.ASSISTANT: "assistant"}
        history = []
        for msg in messages[-20:]:  # Last 20 messages
            mapped_role = role_map.get(msg.role)
            if mapped_role is None:
                continue
            history.append({"role": mapped_role, "content": msg.content})
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

        # Get learner state for grounding
        learner_state = cls._get_learner_state()

        # Build system prompt + per-turn chat history for tool-calling
        system_prompt = coach_prompts.COACH_CHAT_SYSTEM_PROMPT.format(
            due_count=learner_state["due_count"]
        )
        history = cls._format_history_for_tools(messages)

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
                quiz_mode_str = args.get("quiz_mode") or "RECALL"
                quiz_size = args.get("quiz_size") or 10
                try:
                    quiz_mode = QuizMode(quiz_mode_str)
                except ValueError:
                    quiz_mode = QuizMode.RECALL

                # Tool call ends the turn: a short client-side confirmation
                # is enough, no extra LLM round-trip (per ADR).
                assistant_message = await cls.start_quiz_action(
                    thread_id, quiz_mode, quiz_size
                )

            elif result.tool_name == "start_writing":
                args = result.tool_arguments or {}
                topic = args.get("writing_topic") or "Free writing"
                assistant_message = await cls.start_writing_action(
                    thread_id, topic
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
                if thread_obj and thread_obj.title is None and title_result.title:
                    thread_obj.title = title_result.title.strip()
                    session.commit()
        except Exception as e:
            logger.warning(f"Failed to generate thread title for thread {thread_id}: {e}")

    @classmethod
    async def start_quiz_action(
        cls, thread_id: int, mode: QuizMode, size: int
    ) -> ChatMessage:
        """Start a quiz action in a thread.

        Calls the existing QuizService.start_session, then appends a message
        with action_type=QUIZ and action_ref_id=session.id.

        Args:
            thread_id: The thread ID
            mode: The quiz mode
            size: Number of questions

        Returns:
            ChatMessage with action_type=QUIZ and action_ref_id set
        """
        # Start the quiz session
        session, _ = await QuizService.start_session(
            mode=mode,
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
        cls, thread_id: int, topic: str
    ) -> ChatMessage:
        """Start a writing action in a thread.

        Creates a WritingPrompt using WritingService, then appends a message
        with action_type=WRITING and action_ref_id=prompt.id.

        Args:
            thread_id: The thread ID
            topic: The writing topic

        Returns:
            ChatMessage with action_type=WRITING and action_ref_id set
        """
        # Create a writing prompt
        prompt = WritingService.generate_mini_prompt()

        # Update the prompt topic if provided
        if topic:
            with Session() as session:
                from app.db.models.writing import WritingPrompt as WritingPromptModel
                p = session.get(WritingPromptModel, prompt.id)
                if p:
                    p.topic = topic
                    session.commit()

        # Append message with action reference
        message = cls.append_message(
            thread_id=thread_id,
            role=ChatRole.ASSISTANT,
            content=f"Writing session started on: {topic}",
            action_type=ChatActionType.WRITING,
            action_ref_id=prompt.id,
        )

        return message

    @classmethod
    async def on_quiz_graded(cls, thread_id: int, session_id: int) -> ChatMessage:
        """Handle quiz completion - generate follow-up message.

        Called after the user submits quiz answers. Fetches the graded session
        summary and calls the LLM for a follow-up message.

        Args:
            thread_id: The thread ID
            session_id: The quiz session ID

        Returns:
            ChatMessage with the follow-up assistant reply
        """
        # Get graded session
        quiz_session, questions = QuizService.get_session_with_questions(session_id)

        # Build summary context
        total = len(questions)
        correct = sum(1 for q in questions if q.is_correct)
        incorrect = total - correct

        # Get messages for context
        messages = cls.list_messages(thread_id)
        messages_text = cls._format_messages(messages)

        # Format quiz results
        context = {
            "messages": messages_text,
            "total": total,
            "correct": correct,
            "incorrect": incorrect,
        }

        try:
            # Call LLM for follow-up
            result = await ollama_adapter.ollama_adapter.generate(
                task=TaskType.COACH_CHAT_AFTER_QUIZ,
                context=context,
                output_schema=CoachFollowupReply,
            )

            # Persist follow-up message (no action)
            return cls.append_message(
                thread_id=thread_id,
                role=ChatRole.ASSISTANT,
                content=result.reply_text,
            )

        except Exception as e:
            logger.error(f"Failed to generate quiz follow-up for thread {thread_id}: {e}")
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

        # Get messages for context
        messages = cls.list_messages(thread_id)
        messages_text = cls._format_messages(messages)

        context = {
            "messages": messages_text,
            "topic": prompt.topic if prompt.topic else "Writing",
            "word_count": 0,  # Unknown at this point - the prompt was started but not necessarily submitted
            "feedback_points": "Writing session completed",
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
                content=result.reply_text,
            )

        except Exception as e:
            logger.error(f"Failed to generate writing follow-up for thread {thread_id}: {e}")
            return cls.append_message(
                thread_id=thread_id,
                role=ChatRole.ASSISTANT,
                content="Great job completing your writing exercise!",
            )
