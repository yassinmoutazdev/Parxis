"""Ollama adapter implementing Generator and Evaluator protocols.

This module provides the concrete implementation for LLM interactions
using Ollama's chat API with structured output support.

Corresponds to ARCHITECTURE Section 3 (ADR-06) and Section 11.1.
"""

import logging
from typing import Any

import httpx
from pydantic import BaseModel

from app.config import settings

from . import inference_settings

logger = logging.getLogger(__name__)


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
        self.api_key = settings.ollama_api_key
        self.timeout = settings.ollama_timeout_seconds
        self.max_retries = settings.ollama_max_retries

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

    async def evaluate(
        self,
        task: str,
        content: str,
        context: dict[str, Any],
        output_schema: type[BaseModel],
    ) -> BaseModel:
        """Evaluate content based on a task and context.

        Args:
            task: The task identifier (e.g., 'grade_quiz_answer', 'mini_writing_eval')
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
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

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
