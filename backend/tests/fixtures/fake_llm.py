"""Fake Generator and Evaluator for testing.

These fixtures return pre-registered responses keyed by task name,
allowing tests to run without a real LLM.
"""

from typing import Any

from pydantic import BaseModel

from app.llm.interface import Evaluator, Generator


class FakeGenerator(Generator):
    """Fake Generator that returns pre-registered responses."""

    def __init__(self):
        self._responses: dict[str, BaseModel] = {}

    def register(self, task: str, response: BaseModel) -> None:
        """Register a response for a given task.

        Args:
            task: The task identifier
            response: The response to return for this task
        """
        self._responses[task] = response

    async def generate(
        self,
        task: str,
        context: dict[str, Any],
        output_schema: type[BaseModel],
    ) -> BaseModel:
        """Generate content based on task and context.

        Args:
            task: The task identifier
            context: Context data for generation
            output_schema: Pydantic model for output

        Returns:
            Pre-registered response or raise error

        Raises:
            ValueError: If no response is registered for the task
        """
        if task not in self._responses:
            raise ValueError(f"No fake response registered for task: {task}")

        response = self._responses[task]
        # Validate and return
        return output_schema.model_validate(response.model_dump())


class FakeEvaluator(Evaluator):
    """Fake Evaluator that returns pre-registered responses."""

    def __init__(self):
        self._responses: dict[str, BaseModel] = {}

    def register(self, task: str, response: BaseModel) -> None:
        """Register a response for a given task.

        Args:
            task: The task identifier
            response: The response to return for this task
        """
        self._responses[task] = response

    async def evaluate(
        self,
        task: str,
        content: str,
        context: dict[str, Any],
        output_schema: type[BaseModel],
    ) -> BaseModel:
        """Evaluate content based on task and context.

        Args:
            task: The task identifier
            content: The content to evaluate
            context: Context data for evaluation
            output_schema: Pydantic model for output

        Returns:
            Pre-registered response or raise error

        Raises:
            ValueError: If no response is registered for the task
        """
        if task not in self._responses:
            raise ValueError(f"No fake response registered for task: {task}")

        response = self._responses[task]
        # Validate and return
        return output_schema.model_validate(response.model_dump())


# Singleton instances for convenience
fake_generator = FakeGenerator()
fake_evaluator = FakeEvaluator()
