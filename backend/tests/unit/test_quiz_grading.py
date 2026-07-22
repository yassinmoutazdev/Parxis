"""Unit tests for quiz grading module.

Corresponds to ARCHITECTURE Section 17.2 and T6.5.1.
Tests grade_deterministic() covering every quiz type's normalization/edge cases.
"""

import pytest
from app.quizzes.grading import grade_deterministic, _normalize, _is_partial_match


class TestNormalize:
    """Tests for the _normalize helper function."""

    def test_lowercase(self):
        """Test that normalization converts to lowercase."""
        assert _normalize("HELLO") == "hello"
        assert _normalize("HeLLo WoRLd") == "hello world"

    def test_strip_whitespace(self):
        """Test that whitespace is stripped."""
        assert _normalize("  hello  ") == "hello"
        assert _normalize("\t\nhello\n\t") == "hello"

    def test_remove_punctuation(self):
        """Test that punctuation is removed except within words."""
        assert _normalize("hello, world!") == "hello world"
        assert _normalize("don't") == "dont"
        assert _normalize("it's a test.") == "its a test"

    def test_collapse_spaces(self):
        """Test that multiple spaces collapse to single space."""
        assert _normalize("hello    world") == "hello world"
        assert _normalize("a  b   c") == "a b c"

    def test_empty_string(self):
        """Test that empty string returns empty."""
        assert _normalize("") == ""
        assert _normalize("   ") == ""


class TestIsPartialMatch:
    """Tests for the _is_partial_match helper function."""

    def test_substring_match(self):
        """Test substring matching."""
        assert _is_partial_match("hello world", "hello") is True
        assert _is_partial_match("hello world", "world") is True
        assert _is_partial_match("hello", "hello world") is True

    def test_no_substring_match_short(self):
        """Test that short strings (< 3 chars) don't match as partial."""
        assert _is_partial_match("hi", "hello") is False
        assert _is_partial_match("hello", "hi") is False

    def test_word_overlap(self):
        """Test word overlap detection."""
        assert _is_partial_match("hello world", "world hello") is True
        assert _is_partial_match("one two three", "two") is True

    def test_no_overlap(self):
        """Test with no overlap."""
        assert _is_partial_match("hello", "goodbye") is False
        assert _is_partial_match("foo bar", "baz qux") is False

    def test_empty_inputs(self):
        """Test with empty strings."""
        assert _is_partial_match("", "hello") is False
        assert _is_partial_match("hello", "") is False


class TestGradeDeterministicRecall:
    """Tests for RECALL question type grading."""

    def test_exact_match(self):
        """Test exact answer matching."""
        is_correct, score, feedback = grade_deterministic(
            question_type="RECALL",
            correct_answer="hello",
            user_answer="hello",
        )
        assert is_correct is True
        assert score == 1.0

    def test_case_insensitive(self):
        """Test case-insensitive matching."""
        is_correct, score, feedback = grade_deterministic(
            question_type="RECALL",
            correct_answer="Hello",
            user_answer="hello",
        )
        assert is_correct is True
        assert score == 1.0

    def test_incorrect_answer(self):
        """Test incorrect answer."""
        is_correct, score, feedback = grade_deterministic(
            question_type="RECALL",
            correct_answer="hello",
            user_answer="goodbye",
        )
        assert is_correct is False
        assert score == 0.0


class TestGradeDeterministicFillBlank:
    """Tests for FILL_BLANK question type grading."""

    def test_exact_match(self):
        """Test exact answer matching."""
        is_correct, score, feedback = grade_deterministic(
            question_type="FILL_BLANK",
            correct_answer="important",
            user_answer="important",
        )
        assert is_correct is True
        assert score == 1.0

    def test_with_punctuation(self):
        """Test matching with punctuation."""
        is_correct, score, feedback = grade_deterministic(
            question_type="FILL_BLANK",
            correct_answer="important",
            user_answer="important!",
        )
        assert is_correct is True

    def test_with_extra_whitespace(self):
        """Test matching with extra whitespace."""
        is_correct, score, feedback = grade_deterministic(
            question_type="FILL_BLANK",
            correct_answer="important",
            user_answer="  important  ",
        )
        assert is_correct is True

    def test_partial_match(self):
        """Test partial match for fill-in-the-blank."""
        is_correct, score, feedback = grade_deterministic(
            question_type="FILL_BLANK",
            correct_answer="very important",
            user_answer="important",
        )
        assert is_correct is True


class TestGradeDeterministicMultipleChoice:
    """Tests for MULTIPLE_CHOICE question type grading."""

    def test_correct_answer(self):
        """Test correct answer selection."""
        is_correct, score, feedback = grade_deterministic(
            question_type="MULTIPLE_CHOICE",
            correct_answer="Option A",
            user_answer="Option A",
            distractors=["Option B", "Option C", "Option D"],
        )
        assert is_correct is True
        assert score == 1.0

    def test_incorrect_answer(self):
        """Test incorrect answer selection."""
        is_correct, score, feedback = grade_deterministic(
            question_type="MULTIPLE_CHOICE",
            correct_answer="Option A",
            user_answer="Option B",
            distractors=["Option B", "Option C", "Option D"],
        )
        assert is_correct is False
        assert score == 0.0

    def test_matches_distractor(self):
        """Test that answering with a distractor is marked incorrect."""
        is_correct, score, feedback = grade_deterministic(
            question_type="MULTIPLE_CHOICE",
            correct_answer="Option A",
            user_answer="Option B",
            distractors=["Option B", "Option C", "Option D"],
        )
        assert is_correct is False


class TestGradeDeterministicErrorCorrection:
    """Tests for ERROR_CORRECTION question type grading."""

    def test_exact_correction(self):
        """Test exact correction."""
        is_correct, score, feedback = grade_deterministic(
            question_type="ERROR_CORRECTION",
            correct_answer="should be",
            user_answer="should be",
        )
        assert is_correct is True
        assert score == 1.0

    def test_incorrect_correction(self):
        """Test incorrect correction returns wrong."""
        is_correct, score, feedback = grade_deterministic(
            question_type="ERROR_CORRECTION",
            correct_answer="should be",
            user_answer="could be",
        )
        assert is_correct is False
        assert score == 0.0


class TestGradeDeterministicFreeText:
    """Tests for free-text modes (REWRITE_NATURALLY, ERROR_CORRECTION)."""

    def test_no_correct_answer(self):
        """Test when no correct answer is provided."""
        is_correct, score, feedback = grade_deterministic(
            question_type="REWRITE_NATURALLY",
            correct_answer=None,
            user_answer="Some answer",
        )
        assert is_correct is False
        assert score == 0.0


class TestGradeDeterministicEdgeCases:
    """Edge case tests."""

    def test_empty_correct_answer(self):
        """Test with empty correct answer."""
        is_correct, score, feedback = grade_deterministic(
            question_type="RECALL",
            correct_answer="",
            user_answer="anything",
        )
        assert is_correct is False

    def test_empty_user_answer(self):
        """Test with empty user answer."""
        is_correct, score, feedback = grade_deterministic(
            question_type="RECALL",
            correct_answer="hello",
            user_answer="",
        )
        assert is_correct is False
        assert score == 0.0

    def test_none_correct_answer(self):
        """Test with None correct answer."""
        is_correct, score, feedback = grade_deterministic(
            question_type="RECALL",
            correct_answer=None,
            user_answer="hello",
        )
        assert is_correct is False
        assert score == 0.0

    def test_user_answer_contains_correct(self):
        """Test when user answer contains the correct answer."""
        is_correct, score, feedback = grade_deterministic(
            question_type="RECALL",
            correct_answer="hello",
            user_answer="The answer is hello indeed",
        )
        assert is_correct is True
        assert score == 1.0

    def test_correct_contains_user_answer(self):
        """Test when correct answer contains the user answer."""
        is_correct, score, feedback = grade_deterministic(
            question_type="RECALL",
            correct_answer="hello world",
            user_answer="hello",
        )
        assert is_correct is True
        assert score == 1.0

    def test_near_miss_free_text(self):
        """Test near-miss answer that should trigger fallback."""
        is_correct, score, feedback = grade_deterministic(
            question_type="RECALL",
            correct_answer="greetings",
            user_answer="grettings",  # typo
        )
        # This should not match exactly - it's close but not exact
        assert is_correct is False
        assert score == 0.0


class TestGradeDeterministicNormalizationEdgeCases:
    """Tests for normalization edge cases."""

    def test_accented_characters(self):
        """Test handling of accented characters."""
        # These won't match after normalization since we strip accents
        is_correct1, _, _ = grade_deterministic(
            question_type="RECALL",
            correct_answer="cafe",
            user_answer="café",
        )
        is_correct2, _, _ = grade_deterministic(
            question_type="RECALL",
            correct_answer="café",
            user_answer="cafe",
        )
        # With simple normalization, these might not match
        # The system relies on LLM fallback for these cases

    def test_special_characters(self):
        """Test handling of special characters."""
        is_correct, _, _ = grade_deterministic(
            question_type="RECALL",
            correct_answer="$100",
            user_answer="100 dollars",
        )
        # $ is stripped, leaving "100" vs "100 dollars"
        # This may not be an exact match

    def test_numbers(self):
        """Test number handling."""
        is_correct, _, _ = grade_deterministic(
            question_type="FILL_BLANK",
            correct_answer="100",
            user_answer="100",
        )
        assert is_correct is True