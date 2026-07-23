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
from app.llm.schemas import CoachReply
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
        """Format messages for the coach prompt.

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

        # Format messages for prompt
        messages_text = cls._format_messages(messages)

        # Build context for LLM
        context = {
            "messages": messages_text,
            "due_count": learner_state["due_count"],
        }

        # Check if this is the first assistant reply (for title suggestion)
        is_first_reply = not any(m.role == ChatRole.ASSISTANT for m in messages)

        try:
            # Call the LLM
            result = await ollama_adapter.ollama_adapter.generate(
                task=TaskType.COACH_CHAT,
                context=context,
                output_schema=CoachReply,
            )

            # Persist the assistant message
            action_type = ChatActionType.NONE
            action_ref_id = None

            # Handle action if present
            if result.action.action == "START_QUIZ":
                # Determine quiz mode
                quiz_mode_str = result.action.quiz_mode or "RECALL"
                quiz_size = result.action.quiz_size or 10
                try:
                    quiz_mode = QuizMode(quiz_mode_str)
                except ValueError:
                    quiz_mode = QuizMode.RECALL

                # Start the quiz
                chat_msg = await cls.start_quiz_action(thread_id, quiz_mode, quiz_size)
                action_type = ChatActionType.QUIZ
                action_ref_id = chat_msg.action_ref_id

            elif result.action.action == "START_WRITING":
                topic = result.action.writing_topic or "Free writing"
                chat_msg = await cls.start_writing_action(thread_id, topic)
                action_type = ChatActionType.WRITING
                action_ref_id = chat_msg.action_ref_id

            # Always persist the assistant reply
            assistant_message = cls.append_message(
                thread_id=thread_id,
                role=ChatRole.ASSISTANT,
                content=result.reply_text,
                action_type=action_type,
                action_ref_id=action_ref_id,
            )

            # Update thread title if this is first reply and suggestion present
            if is_first_reply and result.suggested_thread_title:
                with Session() as session:
                    thread_obj = session.get(ChatThread, thread_id)
                    if thread_obj and thread_obj.title is None:
                        thread_obj.title = result.suggested_thread_title
                        session.commit()

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
                task=TaskType.COACH_CHAT,  # Use same task type, different prompt would need separate task
                context=context,
                output_schema=CoachReply,
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
                task=TaskType.COACH_CHAT,
                context=context,
                output_schema=CoachReply,
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
