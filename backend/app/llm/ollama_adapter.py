"""Ollama adapter implementing Generator and Evaluator protocols.

This module provides the concrete implementation for LLM interactions
using Ollama's chat API with structured output support.

Corresponds to ARCHITECTURE Section 3 (ADR-06) and Section 11.1.
"""

import logging
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import BaseModel

from app.config import settings
from app.config_service import ConfigService

from . import inference_settings

logger = logging.getLogger(__name__)


class OllamaAuthError(Exception):
    """Raised when Ollama returns a 401/auth failure.

    This is caught by the API layer and translated to a consistent
    `ollama_auth_failed` error shape so the frontend can redirect
    to ConnectScreen from any endpoint.
    """

    def __init__(self, message: str = "Ollama authentication failed"):
        super().__init__(message)


@dataclass
class ToolCallResult:
    """Result of a tool-calling chat turn.

    Exactly one of (tool_name is None) or (content == "") should typically
    hold: the model either replies conversationally, or invokes a tool to
    end the turn (per ADR: tool call ends the turn, no extra round-trip).
    """

    content: str
    tool_name: str | None = None
    tool_arguments: dict[str, Any] | None = None

    @property
    def is_tool_call(self) -> bool:
        return self.tool_name is not None


def _strip_code_fences(content: str) -> str:
    """Strip markdown code fences from JSON content.

    Sometimes the model wraps JSON in ```json ... ``` fences even when
    format=schema is specified. This removes those fences.

    Args:
        content: The raw content from the model

    Returns:
        Content with code fences stripped
    """
    # Strip ```json and ``` markers
    lines = content.split("\n")
    cleaned_lines = []

    for line in lines:
        # Skip code fence markers
        if line.strip() in ("```json", "```", "`json", "`"):
            continue
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


class OllamaAdapter:
    """Ollama implementation of Generator and Evaluator protocols.

    Uses httpx.AsyncClient for async HTTP calls to Ollama's /api/chat endpoint.
    Supports schema-constrained output via the `format` parameter.
    """

    def __init__(self, host: str | None = None, model: str | None = None):
        """Initialize the Ollama adapter.

        Args:
            host: Ollama host URL (defaults to settings.ollama_host)
            model: Model name (defaults to settings.ollama_model)
        """
        self.host = host or settings.ollama_host
        self.model = model or settings.ollama_model
        # API key is now loaded from ConfigService at call time, not init
        self.timeout = settings.ollama_timeout_seconds
        self.max_retries = settings.ollama_max_retries

    def _get_api_key(self) -> str | None:
        """Get the current API key from ConfigService (runtime value)."""
        try:
            key = ConfigService.get("ollama_api_key")
            return key if key and key.strip() else None
        except Exception:
            return None

    async def test_auth(self, api_key: str) -> None:
        """Test an API key against Ollama by making a cheap models list call.

        Args:
            api_key: The API key to test

        Raises:
            OllamaAuthError: If the key is rejected (401)
            httpx.ConnectError/TimeoutException: Network issues
            Exception: Other errors
        """
        headers = {"Authorization": f"Bearer {api_key}"}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.host}/api/tags",
                headers=headers,
            )
            if response.status_code == 401:
                raise OllamaAuthError("API key rejected by Ollama")
            response.raise_for_status()

    async def generate(
        self,
        task: str,
        context: dict[str, Any],
        output_schema: type[BaseModel],
    ) -> BaseModel:
        """Generate content based on a task and context.

        Args:
            task: The task identifier (e.g., 'parse_note', 'quiz_recall')
            context: Context data for the generation task
            output_schema: Pydantic model class defining the expected output structure

        Returns:
            An instance of the output_schema with generated content

        Raises:
            httpx.ConnectError: If Ollama is unreachable after retries
            httpx.TimeoutException: If the request times out
            Exception: If generation fails after retries
        """
        from .prompts import get_prompt_template
        from .prompts.parser import build_parse_note_context

        # Build context for specific tasks that need preprocessing
        if task == "parse_note":
            formatted_context = build_parse_note_context(
                note_content=context.get("note_content", ""),
                recent_item_texts=context.get("recent_item_texts"),
            )
        else:
            formatted_context = context

        prompt_template = get_prompt_template(task)
        user_message = prompt_template.format(**formatted_context)

        return await self._call_with_retry(
            task=task,
            messages=[{"role": "user", "content": user_message}],
            output_schema=output_schema,
        )

    async def generate_chat_with_tools(
        self,
        task: str,
        system_prompt: str,
        history: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ToolCallResult:
        """Run a chat turn with real Ollama tool-calling (not schema-forced JSON).

        Sends a proper chat message list (system + per-turn user/assistant
        messages) plus a `tools` spec, and reads back either free-text content
        or a tool call from `message.tool_calls`, per Ollama's native
        function-calling API.

        Args:
            task: The task identifier, used for inference settings lookup
            system_prompt: The system message content
            history: Prior turns as [{"role": "user"|"assistant", "content":
                str, "images"?: list[str]}] -- the optional per-message
                `images` field carries base64-encoded attachment bytes for
                Ollama's native multimodal chat API
            tools: Ollama tool specs (see app.llm.tools)

        Returns:
            ToolCallResult with either conversational content, or a tool call

        Raises:
            httpx.ConnectError: If Ollama is unreachable after retries
            httpx.TimeoutException: If the request times out
            OllamaAuthError: If API key is rejected (401)
        """
        messages = [{"role": "system", "content": system_prompt}, *history]
        inf_settings = inference_settings.get_settings_for_task(task)

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "stream": False,
            **inf_settings.to_ollama_params(),
        }

        headers: dict[str, str] = {}
        api_key = self._get_api_key()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            last_error: Exception | None = None

            for attempt in range(self.max_retries + 1):
                try:
                    response = await client.post(
                        f"{self.host}/api/chat",
                        json=payload,
                        headers=headers,
                    )
                    response.raise_for_status()

                    data = response.json()
                    message = data.get("message", {})
                    tool_calls = message.get("tool_calls") or []
                    content = message.get("content", "") or ""

                    if tool_calls:
                        # Only ever act on the first tool call (prompt instructs
                        # the model not to call more than one per turn).
                        call = tool_calls[0].get("function", {})
                        name = call.get("name")
                        arguments = call.get("arguments") or {}
                        if name:
                            return ToolCallResult(
                                content=content,
                                tool_name=name,
                                tool_arguments=arguments,
                            )
                        # Malformed tool call (no name) -- treat as retryable.
                        logger.warning(
                            f"Tool call missing function name for task {task}: {tool_calls[0]}"
                        )
                        if attempt < self.max_retries:
                            last_error = ValueError("Malformed tool call")
                            continue
                        # Fall through to plain content as a last resort.

                    if content.strip():
                        return ToolCallResult(content=content)

                    # Empty response with no tool call -- retry once, then
                    # fall back to a generic message rather than failing hard.
                    logger.warning(
                        f"Empty content and no tool_calls for task {task} "
                        f"(attempt {attempt + 1})"
                    )
                    if attempt < self.max_retries:
                        last_error = ValueError("Empty model response")
                        continue
                    return ToolCallResult(
                        content="Sorry, could you say that again?"
                    )

                except httpx.ConnectError as e:
                    logger.warning(f"Connection error on attempt {attempt + 1}: {e}")
                    last_error = e
                    import asyncio

                    await asyncio.sleep(1 if attempt == 0 else 3)
                    continue

                except httpx.TimeoutException:
                    logger.error(f"Timeout after {self.timeout}s for task {task}")
                    raise

                except httpx.HTTPStatusError as e:
                    # Intercept 401 auth errors and raise OllamaAuthError
                    if e.response.status_code == 401:
                        raise OllamaAuthError("Ollama authentication failed - API key may be invalid or expired")

                    # Fallback path: some Ollama versions/models reject the
                    # `tools` param outright (400) instead of just ignoring
                    # unsupported tool calls. Retry once as a plain chat
                    # call so the coach still responds conversationally.
                    if e.response.status_code == 400 and "tools" in payload:
                        logger.warning(
                            f"Ollama rejected tools param for task {task}, "
                            "falling back to plain chat without tools"
                        )
                        payload = {k: v for k, v in payload.items() if k != "tools"}
                        last_error = e
                        continue
                    logger.error(f"HTTP error for task {task}: {e}")
                    raise

            if last_error:
                raise last_error
            raise Exception(f"Failed after {self.max_retries + 1} attempts")

    def generate_sync(
        self,
        task: str,
        context: dict[str, Any],
        output_schema: type[BaseModel],
    ) -> BaseModel:
        """Synchronous wrapper for generate.

        Args:
            task: The task identifier
            context: Context data for the generation task
            output_schema: Pydantic model class defining the expected output structure

        Returns:
            An instance of the output_schema with generated content
        """
        import asyncio

        return asyncio.run(self.generate(task, context, output_schema))

    async def evaluate(
        self,
        task: str,
        content: str,
        context: dict[str, Any],
        output_schema: type[BaseModel],
    ) -> BaseModel:
        """Evaluate content based on a task and context.

        Args:
            task: The task identifier (e.g., 'mini_writing_eval', 'weekly_writing_eval')
            content: The content to evaluate
            context: Context data for the evaluation task
            output_schema: Pydantic model class defining the expected output structure

        Returns:
            An instance of the output_schema with evaluation results

        Raises:
            httpx.ConnectError: If Ollama is unreachable after retries
            httpx.TimeoutException: If the request times out
            Exception: If evaluation fails after retries
        """
        from .prompts import get_prompt_template

        # Add content to context for prompt formatting
        full_context = {**context, "content": content}
        prompt_template = get_prompt_template(task)
        user_message = prompt_template.format(**full_context)

        return await self._call_with_retry(
            task=task,
            messages=[{"role": "user", "content": user_message}],
            output_schema=output_schema,
        )

    async def _call_with_retry(
        self,
        task: str,
        messages: list[dict[str, str]],
        output_schema: type[BaseModel],
        retry_message: str | None = None,
    ) -> BaseModel:
        """Make an Ollama API call with retry logic.

        Corresponds to ARCHITECTURE Section 11.2 (General Retry Discipline).

        Args:
            task: The task identifier
            messages: List of message dicts with role and content
            output_schema: Pydantic model class for structured output
            retry_message: Optional correction instruction for retry

        Returns:
            An instance of the output_schema with validated content

        Raises:
            httpx.ConnectError: If Ollama is unreachable after retries
            httpx.TimeoutException: If the request times out
            Exception: If all retries fail
        """
        # If this is a retry, append the correction instruction
        if retry_message:
            messages[-1]["content"] += f"\n\n{retry_message}"

        # Get inference settings for this task
        inf_settings = inference_settings.get_settings_for_task(task)

        # Build request payload
        payload = {
            "model": self.model,
            "messages": messages,
            "format": output_schema.model_json_schema(),
            "stream": False,  # Disable streaming for structured output
            **inf_settings.to_ollama_params(),
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            last_error: Exception | None = None

            # Build request headers (include API key if set)
            headers: dict[str, str] = {}
            api_key = self._get_api_key()
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            for attempt in range(self.max_retries + 1):
                try:
                    response = await client.post(
                        f"{self.host}/api/chat",
                        json=payload,
                        headers=headers,
                    )
                    response.raise_for_status()

                    data = response.json()
                    content = data.get("message", {}).get("content", "")

                    # Strip markdown code fences if present
                    content = _strip_code_fences(content)

                    # Handle case where model returns array instead of object
                    if content.strip().startswith("["):
                        content = '{"items": ' + content + "}"

                    # Parse and validate the response
                    try:
                        return output_schema.model_validate_json(content)
                    except Exception as e:
                        logger.warning(
                            f"Schema validation failed for task {task}: {e}"
                        )
                        # Retry with correction instruction
                        if attempt < self.max_retries:
                            last_error = e
                            continue
                        raise

                except httpx.ConnectError as e:
                    logger.warning(
                        f"Connection error on attempt {attempt + 1}: {e}"
                    )
                    last_error = e
                    # Exponential backoff: 1s, 3s
                    import asyncio

                    await asyncio.sleep(1 if attempt == 0 else 3)
                    continue

                except httpx.TimeoutException:
                    # No retry on timeout (per Architecture Section 11.1)
                    logger.error(f"Timeout after {self.timeout}s for task {task}")
                    raise

                except httpx.HTTPStatusError as e:
                    # Intercept 401 auth errors and raise OllamaAuthError
                    if e.response.status_code == 401:
                        raise OllamaAuthError("Ollama authentication failed - API key may be invalid or expired")
                    logger.error(f"HTTP error for task {task}: {e}")
                    raise

                except Exception as e:
                    logger.error(f"Unexpected error for task {task}: {e}")
                    raise

            # All retries exhausted
            if last_error:
                raise last_error
            raise Exception(f"Failed after {self.max_retries + 1} attempts")


# Module-level instance for convenience
ollama_adapter = OllamaAdapter()
