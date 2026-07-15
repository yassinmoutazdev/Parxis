"""Inference settings lookup for different task types.

Corresponds to ARCHITECTURE Section 3 (ADR-12) - deterministic inference
settings for grading and evaluation calls.
"""

from dataclasses import dataclass
from typing import Any

from app.llm.interface import TaskType


@dataclass
class InferenceSettings:
    """Inference parameters for LLM calls.

    Corresponds to ARCHITECTURE Section 9's note on deterministic settings.
    """

    temperature: float = 0.7
    seed: int | None = None
    top_p: float | None = None
    repeat_penalty: float | None = None

    def to_ollama_params(self) -> dict[str, Any]:
        """Convert settings to Ollama API parameters."""
        params: dict[str, Any] = {"temperature": self.temperature}

        if self.seed is not None:
            params["seed"] = self.seed
        if self.top_p is not None:
            params["top_p"] = self.top_p
        if self.repeat_penalty is not None:
            params["repeat_penalty"] = self.repeat_penalty

        return params


# Grading/evaluation tasks need deterministic settings (ADR-12)
_GRADING_SETTINGS = InferenceSettings(
    temperature=0.0,
    seed=42,  # Fixed seed for reproducibility
)

# Generation tasks use default sampling for variety
_DEFAULT_SETTINGS = InferenceSettings(
    temperature=0.7,
)

# Lookup table mapping task names to settings
_TASK_SETTINGS: dict[str, InferenceSettings] = {
    TaskType.GRADE_QUIZ_ANSWER: _GRADING_SETTINGS,
    TaskType.MINI_WRITING_EVAL: _GRADING_SETTINGS,
    TaskType.WEEKLY_WRITING_EVAL: _GRADING_SETTINGS,
}


def get_settings_for_task(task: str) -> InferenceSettings:
    """Get inference settings for a given task.

    Args:
        task: The task identifier (e.g., 'grade_quiz_answer')

    Returns:
        InferenceSettings configured for the task type

    Note:
        Grading/evaluation tasks (grade_quiz_answer, mini_writing_eval,
        weekly_writing_eval) use deterministic settings (temperature=0, seed=42)
        per ADR-12. All other tasks use default sampling.
    """
    return _TASK_SETTINGS.get(task, _DEFAULT_SETTINGS)
