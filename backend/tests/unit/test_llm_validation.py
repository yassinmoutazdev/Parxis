"""Unit tests for LLM validation functions.

Corresponds to ARCHITECTURE Section 17.2 (Testing Boundaries).
"""


from app.llm.schemas import (
    DimensionScore,
    GradedAnswerOutput,
    MiniWritingEvalOutput,
    ParsedItem,
    ParsedNoteOutput,
    QuizQuestionOutput,
    TopicOutput,
    WeeklyNarrativeOutput,
    WeeklyWritingEvalOutput,
)
from app.llm.validation import (
    validate_graded_answer,
    validate_mini_writing_eval,
    validate_parsed_note,
    validate_quiz_question,
    validate_topic,
    validate_weekly_narrative,
    validate_weekly_writing_eval,
)


class TestValidateParsedNote:
    """Tests for validate_parsed_note (Section 9.1)."""

    def test_valid_parsed_note(self):
        """Valid parsed note passes validation."""
        output = ParsedNoteOutput(
            items=[
                ParsedItem(
                    item_type="IDIOM",
                    text="break the ice",
                    definition="To start a conversation",
                    example_sentence="Let me break the ice.",
                    source_excerpt="Let me break the ice.",
                )
            ]
        )
        note_content = "Let me break the ice."

        result, warnings = validate_parsed_note(output, note_content)

        assert len(result.items) == 1
        assert len(warnings) == 0

    def test_source_excerpt_not_in_note(self):
        """source_excerpt not in note produces warning."""
        output = ParsedNoteOutput(
            items=[
                ParsedItem(
                    item_type="IDIOM",
                    text="break the ice",
                    source_excerpt="Paraphrased content",  # Not in note
                )
            ]
        )
        note_content = "Let me break the ice."

        result, warnings = validate_parsed_note(output, note_content)

        assert len(warnings) == 1
        assert "source_excerpt is not a verbatim quote" in warnings[0]

    def test_correction_missing_fields_downgrades(self):
        """CORRECTION without both fields downgrades to PERSONAL_EXAMPLE."""
        # Create via model_validate to bypass Pydantic validation
        item_data = {
            "item_type": "CORRECTION",
            "text": "wrong usage",
            "wrong_form": "irregardless",
            # Missing correct_form
            "source_excerpt": "test",
        }
        item = ParsedItem.model_validate(item_data)
        output = ParsedNoteOutput(items=[item])
        note_content = "test note"

        result, warnings = validate_parsed_note(output, note_content)

        assert result.items[0].item_type == "PERSONAL_EXAMPLE"
        assert len(warnings) == 1

    def test_correction_with_both_fields_valid(self):
        """CORRECTION with both fields passes validation."""
        output = ParsedNoteOutput(
            items=[
                ParsedItem(
                    item_type="CORRECTION",
                    text="irregardless",
                    wrong_form="irregardless",
                    correct_form="regardless",
                    source_excerpt="Use irregardless",
                )
            ]
        )
        note_content = "Use irregardless"

        result, warnings = validate_parsed_note(output, note_content)

        assert result.items[0].item_type == "CORRECTION"
        assert len(warnings) == 0


class TestValidateQuizQuestion:
    """Tests for validate_quiz_question (Section 9.2 - multiple choice only)."""

    def test_multiple_choice_valid(self):
        """Valid multiple choice passes."""
        output = QuizQuestionOutput(
            prompt_text="What does X mean?",
            correct_answer="the meaning",
            distractors=["wrong1", "wrong2", "wrong3"],
        )

        result, warnings = validate_quiz_question(output)

        assert result is not None
        assert len(warnings) == 0

    def test_multiple_choice_wrong_distractor_count(self):
        """Wrong number of distractors fails."""
        output = QuizQuestionOutput(
            prompt_text="What does X mean?",
            correct_answer="the meaning",
            distractors=["wrong1"],  # Only 1
        )

        result, warnings = validate_quiz_question(output)

        assert result is None
        assert "exactly 3 distractors" in warnings[0]

    def test_multiple_choice_distractor_matches_answer(self):
        """Distractor matching correct answer fails."""
        output = QuizQuestionOutput(
            prompt_text="What does X mean?",
            correct_answer="the meaning",
            distractors=["the meaning", "wrong2", "wrong3"],
        )

        result, warnings = validate_quiz_question(output)

        assert result is None
        assert "distractor matches" in warnings[0]


class TestValidateGradedAnswer:
    """Tests for validate_graded_answer (Section 9.3)."""

    def test_score_in_range(self):
        """Score in valid range passes."""
        output = GradedAnswerOutput(score=0.85, feedback="Good")

        result = validate_graded_answer(output)

        assert result.score == 0.85

    def test_score_above_max_clamped(self):
        """Score above 1.0 is clamped to 1.0."""
        # Create via model_validate to bypass schema constraints
        data = {"score": 1.5, "feedback": "Good"}
        output = GradedAnswerOutput.model_validate(data)

        result = validate_graded_answer(output)

        assert result.score == 1.0

    def test_score_below_min_clamped(self):
        """Score below 0.0 is clamped to 0.0."""
        # Create via model_validate to bypass schema constraints
        data = {"score": -0.5, "feedback": "Good"}
        output = GradedAnswerOutput.model_validate(data)

        result = validate_graded_answer(output)

        assert result.score == 0.0


class TestValidateMiniWritingEval:
    """Tests for validate_mini_writing_eval (Section 9.4)."""

    def test_naturalness_notes_within_limit(self):
        """naturalness_notes within limit passes."""
        output = MiniWritingEvalOutput(
            corrections=[],
            naturalness_notes=["note1", "note2"],
        )

        result = validate_mini_writing_eval(output)

        assert len(result.naturalness_notes) == 2

    def test_naturalness_notes_truncated(self):
        """naturalness_notes over 2 are truncated."""
        output = MiniWritingEvalOutput(
            corrections=[],
            naturalness_notes=["note1", "note2", "note3", "note4"],
        )

        result = validate_mini_writing_eval(output)

        assert len(result.naturalness_notes) == 2


class TestValidateWeeklyWritingEval:
    """Tests for validate_weekly_writing_eval (Section 9.5 + Part B CEFR)."""

    def test_scores_in_range(self):
        """Scores in valid range pass."""
        output = WeeklyWritingEvalOutput(
            grammar=DimensionScore(score=85, feedback="Good"),
            naturalness=DimensionScore(score=80, feedback="Good"),
            vocabulary=DimensionScore(score=75, feedback="Good"),
            coherence=DimensionScore(score=90, feedback="Good"),
            overall=DimensionScore(score=82, feedback="Good overall"),
            cefr_band="B2",
            band_justification="Demonstrates good command of language with minor errors.",
        )

        result, warnings = validate_weekly_writing_eval(output)

        assert len(warnings) == 0

    def test_scores_clamped(self):
        """Scores outside [0, 100] are clamped."""
        # Create via model_validate to bypass schema constraints
        data = {
            "grammar": {"score": 150, "feedback": "Good"},
            "naturalness": {"score": -20, "feedback": "Good"},
            "vocabulary": {"score": 75, "feedback": "Good"},
            "coherence": {"score": 90, "feedback": "Good"},
            "overall": {"score": 82, "feedback": "Good"},
            "cefr_band": "B2",
            "band_justification": "Test justification",
        }
        output = WeeklyWritingEvalOutput.model_validate(data)

        result, warnings = validate_weekly_writing_eval(output)

        assert result.grammar.score == 100.0
        assert result.naturalness.score == 0.0

    def test_empty_band_justification_warning(self):
        """Empty band_justification produces warning."""
        output = WeeklyWritingEvalOutput(
            grammar=DimensionScore(score=85, feedback="Good"),
            naturalness=DimensionScore(score=80, feedback="Good"),
            vocabulary=DimensionScore(score=75, feedback="Good"),
            coherence=DimensionScore(score=90, feedback="Good"),
            overall=DimensionScore(score=82, feedback="Good overall"),
            cefr_band="B2",
            band_justification="",  # Empty
        )

        result, warnings = validate_weekly_writing_eval(output)

        assert len(warnings) == 1
        assert "band_justification" in warnings[0]


class TestValidateWeeklyNarrative:
    """Tests for validate_weekly_narrative (Section 9.6)."""

    def test_word_count_in_range(self):
        """Word count within 100-400 passes."""
        output = WeeklyNarrativeOutput(
            narrative_report=" ".join(["word"] * 200),
            top_strengths_this_week=["strength1"],
            top_focus_areas_next_week=["focus1"],
        )

        result, warnings = validate_weekly_narrative(output)

        assert len(warnings) == 0

    def test_word_count_outside_range_warning(self):
        """Word count outside range produces warning."""
        output = WeeklyNarrativeOutput(
            narrative_report=" ".join(["word"] * 50),  # Too short
            top_strengths_this_week=["strength1"],
            top_focus_areas_next_week=["focus1"],
        )

        result, warnings = validate_weekly_narrative(output)

        assert len(warnings) == 1
        assert "word count" in warnings[0]


class TestValidateTopic:
    """Tests for validate_topic (Section 9.7)."""

    def test_topic_not_in_recent(self):
        """Topic not in recent topics passes."""
        output = TopicOutput(
            topic="travel",
            prompt_text="Write about travel",
        )
        recent_topics = ["cooking", "sports", "music"]

        result, warnings = validate_topic(output, recent_topics)

        assert len(warnings) == 0

    def test_topic_matches_recent(self):
        """Topic matching recent topic produces warning."""
        output = TopicOutput(
            topic="cooking",
            prompt_text="Write about cooking",
        )
        recent_topics = ["cooking", "sports", "music"]

        result, warnings = validate_topic(output, recent_topics)

        assert len(warnings) == 1
        assert "matches recent topic" in warnings[0]

    def test_topic_case_insensitive_match(self):
        """Case-insensitive matching works."""
        output = TopicOutput(
            topic="COOKING",
            prompt_text="Write about cooking",
        )
        recent_topics = ["cooking", "sports"]

        result, warnings = validate_topic(output, recent_topics)

        assert len(warnings) == 1
