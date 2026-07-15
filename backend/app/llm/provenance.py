"""Provenance stamping helper for LLM evaluation results.

Corresponds to ARCHITECTURE Section 3 (ADR-13) - evaluation versioning.

This module provides a helper for calling services to populate
evaluator_provider, evaluator_model, prompt_version, and rubric_version
on graded/evaluated rows.
"""

from dataclasses import dataclass

from app.config import settings


@dataclass
class EvaluationProvenance:
    """Provenance metadata for LLM evaluation results.

    Corresponds to ARCHITECTURE Section 7.1 (v1.1 Evaluation metadata).

    This data is stamped by the calling service, not the model.
    """

    evaluator_provider: str = "ollama"
    evaluator_model: str = ""  # Populated from settings at call time
    prompt_version: str = ""
    rubric_version: str | None = None


def stamp_provenance(
    prompt_version: str,
    rubric_version: str | None = None,
) -> EvaluationProvenance:
    """Create a provenance stamp for an LLM evaluation.

    Args:
        prompt_version: Version identifier for the prompt template used
        rubric_version: Version identifier for the rubric used (optional,
                       for writing evaluation tasks only)

    Returns:
        EvaluationProvenance with all fields populated

    Note:
        - evaluator_provider is always "ollama"
        - evaluator_model is read from settings at call time
        - prompt_version must be provided (co-located with the template)
        - rubric_version is optional (per ADR-13's independent versioning)
    """
    return EvaluationProvenance(
        evaluator_provider="ollama",
        evaluator_model=settings.ollama_model,
        prompt_version=prompt_version,
        rubric_version=rubric_version,
    )


def to_dict(provenance: EvaluationProvenance) -> dict[str, str | None]:
    """Convert provenance to a dictionary for database insertion.

    Args:
        provenance: The provenance metadata to convert

    Returns:
        Dictionary with provenance fields
    """
    return {
        "evaluator_provider": provenance.evaluator_provider,
        "evaluator_model": provenance.evaluator_model,
        "prompt_version": provenance.prompt_version,
        "rubric_version": provenance.rubric_version,
    }
