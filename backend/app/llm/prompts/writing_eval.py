"""Writing evaluation prompt templates.

Corresponds to ARCHITECTURE Sections 9.4 (Mini) and 9.5 (Weekly).
"""

# Prompt version constants (ADR-13)
MINI_WRITING_EVAL_PROMPT_VERSION = "1.0.0"
MINI_WRITING_EVAL_RUBRIC_VERSION = "1.0.0"
WEEKLY_WRITING_EVAL_PROMPT_VERSION = "2.1.0"
WEEKLY_WRITING_EVAL_RUBRIC_VERSION = "2.0.0"

# Rubric text blocks (separately versioned per ADR-13)
MINI_WRITING_EVAL_RUBRIC = """Evaluate the writing based on:

1. Grammar: Check for grammatical errors
2. Naturalness: Evaluate if the writing sounds natural for a native speaker
3. Vocabulary: Assess word choice appropriateness

Provide corrections for any errors found.
Limit naturalness_notes to 2 items maximum."""


WEEKLY_WRITING_EVAL_RUBRIC = """Evaluate this submission against the CEFR writing descriptors below.
Select exactly ONE band that best matches the submission, and justify
your choice by pointing to specific features of the text (not just
restating the descriptor).

A2: Can write short, simple connected text on familiar topics. Frequent
    basic errors; limited range of vocabulary and structures.
B1: Can write straightforward connected text on familiar topics.
    Generally understandable despite noticeable errors; some ability to
    link ideas, but limited variety of structures.
B2: Can write clear, detailed text on a range of subjects. Good control
    of grammar; errors don't obscure meaning; reasonable range of
    vocabulary and some idiomatic usage; ideas are logically organized.
C1: Can write clear, well-structured text with an effective logical
    structure. Wide range of vocabulary and grammar used flexibly and
    accurately; only occasional, minor errors; register is consistently
    appropriate.
C2: Can write clear, smoothly flowing, complex text in an appropriate,
    effective style. Precise, idiomatic control of language; errors are
    vanishingly rare; nuanced and natural throughout.

Also score these supporting dimensions (0-100), consistent with the band
you selected -- they should read as evidence for the band, not a
contradiction of it:

1. Grammar (0-100)
2. Naturalness (0-100)
3. Vocabulary (0-100)
4. Coherence (0-100)

Provide specific feedback for each dimension."""


# Mini writing evaluation prompt
MINI_WRITING_EVAL_PROMPT = """You are a writing teacher. Evaluate the learner's mini writing submission.

Submission:
{submission_text}

{focus_areas}

{RUBRIC}

Generate your evaluation in JSON format:
{
    "corrections": [
        {"wrong": "the error", "correct": "the correction", "explanation": "why"}
    ],
    "naturalness_notes": ["note 1", "note 2"],
    "suggested_items": []
}

Important:
- Limit naturalness_notes to exactly 2 items
- suggested_items should be empty for mini writing (only for weekly)
Return valid JSON only."""


# Weekly writing evaluation prompt
WEEKLY_WRITING_EVAL_PROMPT = """You are a writing teacher. Evaluate the learner's weekly writing submission.

Submission:
{submission_text}

Weak areas to focus on:
{weak_categories}

Known relevant items from your knowledge base:
{known_relevant_items}

{RUBRIC}

Generate your evaluation in JSON format:
{
    "cefr_band": "B2",
    "band_justification": "The text demonstrates clear, detailed writing on a range of subjects with good grammar control...",
    "grammar": {"score": 85, "feedback": "Good grammar overall..."},
    "naturalness": {"score": 80, "feedback": "Sounds natural..."},
    "vocabulary": {"score": 75, "feedback": "Could use more varied vocabulary..."},
    "coherence": {"score": 90, "feedback": "Well organized..."},
    "suggested_items": [
        {
            "item_type": "COLLOCATION",
            "text": "...",
            "definition": "...",
            "example_sentence": "...",
            "source_excerpt": "verbatim span from the submission this was drawn from",
            "confidence": "high",
            "low_confidence_reason": null,
            "possible_duplicate_reason": null
        }
    ]
}

suggested_items are learnable items worth adding to the learner's knowledge
base based on this submission (e.g. a correction pattern the learner keeps
needing, a collocation they used well and should reinforce). Same fields and
rules as note extraction:
- definition and example_sentence are REQUIRED for all non-CORRECTION types
- confidence: "high" | "medium" | "low" - your self-reported confidence
- low_confidence_reason: REQUIRED whenever confidence is "low". Name the
  SPECIFIC ambiguity (not a generic "not sure") - this text is reused
  directly as a retry instruction and, if still unresolved, as a question
  back to the learner.
- possible_duplicate_reason: only if you suspect overlap with
  known_relevant_items above, even if wording differs
- Leave suggested_items empty if nothing in the submission is worth adding

Important:
- cefr_band must be exactly one of: A1, A2, B1, B2, C1, C2
- band_justification must be non-empty and reference specific text features
- All scores must be between 0 and 100
- Scores must be consistent with the selected CEFR band
Return valid JSON only."""


def get_mini_writing_eval_prompt() -> str:
    """Get the mini writing evaluation prompt template.

    Returns:
        The prompt template string with rubric substituted
    """
    return MINI_WRITING_EVAL_PROMPT.replace("{RUBRIC}", MINI_WRITING_EVAL_RUBRIC)


def get_weekly_writing_eval_prompt() -> str:
    """Get the weekly writing evaluation prompt template.

    Returns:
        The prompt template string with rubric substituted
    """
    return WEEKLY_WRITING_EVAL_PROMPT.replace("{RUBRIC}", WEEKLY_WRITING_EVAL_RUBRIC)


def get_mini_writing_eval_versions() -> tuple[str, str]:
    """Get prompt and rubric versions for mini writing evaluation.

    Returns:
        Tuple of (prompt_version, rubric_version)
    """
    return (MINI_WRITING_EVAL_PROMPT_VERSION, MINI_WRITING_EVAL_RUBRIC_VERSION)


def get_weekly_writing_eval_versions() -> tuple[str, str]:
    """Get prompt and rubric versions for weekly writing evaluation.

    Returns:
        Tuple of (prompt_version, rubric_version)
    """
    return (WEEKLY_WRITING_EVAL_PROMPT_VERSION, WEEKLY_WRITING_EVAL_RUBRIC_VERSION)