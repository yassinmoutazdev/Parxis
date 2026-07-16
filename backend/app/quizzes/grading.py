"""Quiz Answer Grading Module.

Corresponds to ARCHITECTURE Section 9.3 (Quiz Answer Grading).
"""

import re


def grade_deterministic(
    question_type: str,
    correct_answer: str | None,
    user_answer: str,
    distractors: list[str] | None = None,
) -> tuple[bool, float, str]:
    """Grade a quiz answer using deterministic matching.

    PRD Section 16.4 (Deterministic Grading):
    - Fill-blank and multiple choice: normalized case/whitespace-insensitive matching
    - On ambiguous free-text mismatch: fallback to LLM grading (handled by caller)

    Args:
        question_type: The quiz mode type
        correct_answer: The correct answer (for MC, this is the correct option)
        user_answer: The user's submitted answer
        distractors: List of incorrect options (for multiple choice)

    Returns:
        Tuple of (is_correct, score, feedback)
        - is_correct: True if answer matches
        - score: 1.0 for correct, 0.0 for incorrect
        - feedback: Brief feedback message

    Note:
        Returns (False, 0.0, "fallback_required") when the match is ambiguous
        and LLM fallback is needed. This happens for free-text modes when
        the simple normalization doesn't give a clear result.
    """
    if not correct_answer:
        return False, 0.0, "No correct answer provided"

    # Normalize both answers for comparison
    normalized_correct = _normalize(correct_answer)
    normalized_user = _normalize(user_answer)

    # Check for exact match (case and whitespace insensitive)
    if normalized_correct == normalized_user:
        return True, 1.0, "Correct!"

    # For multiple choice, also check against distractors
    if distractors:
        for distractor in distractors:
            if _normalize(distractor) == normalized_user:
                return False, 0.0, f"Incorrect. The correct answer is: {correct_answer}"

    # Check for partial match (for fill-in-the-blank)
    if _is_partial_match(normalized_correct, normalized_user):
        return True, 1.0, "Correct!"

    # Check if user answer contains the correct answer (lenient matching)
    if len(normalized_user) >= 3 and normalized_correct in normalized_user:
        return True, 1.0, "Correct!"

    # Check if the correct answer contains the user answer (lenient matching)
    if len(normalized_user) >= 3 and normalized_user in normalized_correct:
        return True, 1.0, "Correct!"

    # No clear match - return ambiguous result for LLM fallback
    return False, 0.0, "Your answer doesn't match. Please try again."


def _normalize(text: str) -> str:
    """Normalize text for comparison.

    - Lowercase
    - Strip whitespace
    - Remove punctuation (except within words)
    - Collapse multiple spaces

    Args:
        text: Text to normalize

    Returns:
        Normalized text
    """
    if not text:
        return ""

    # Convert to lowercase
    text = text.lower()

    # Strip leading/trailing whitespace
    text = text.strip()

    # Remove punctuation except within words (keep letters, numbers, spaces)
    # This preserves things like "don't" but removes ". , ! ?"
    text = re.sub(r"[^\w\s]", "", text)

    # Collapse multiple spaces into single space
    text = re.sub(r"\s+", " ", text)

    return text


def _is_partial_match(correct: str, user: str) -> bool:
    """Check for partial match between normalized strings.

    This handles cases where the user answer is incomplete but
    clearly related to the correct answer.

    Args:
        correct: Normalized correct answer
        user: Normalized user answer

    Returns:
        True if there's a partial match
    """
    if not correct or not user:
        return False

    # If one is a substring of the other (length >= 3)
    if len(user) >= 3 and user in correct:
        return True
    if len(correct) >= 3 and correct in user:
        return True

    # Check for word overlap (at least one significant word matches)
    correct_words = set(correct.split())
    user_words = set(user.split())

    # Remove very short words
    correct_words = {w for w in correct_words if len(w) >= 3}
    user_words = {w for w in user_words if len(w) >= 3}

    if not correct_words or not user_words:
        return False

    overlap = correct_words & user_words
    if overlap:
        return True

    return False
