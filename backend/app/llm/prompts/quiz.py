"""Quiz generation prompt templates.

Corresponds to ARCHITECTURE Section 9.2 (Quiz Generator).
"""

# Version constants for each quiz mode (ADR-13)
QUIZ_RECALL_PROMPT_VERSION = "1.0.0"
QUIZ_FILL_BLANK_PROMPT_VERSION = "1.0.0"
QUIZ_MULTIPLE_CHOICE_PROMPT_VERSION = "1.0.0"
QUIZ_ERROR_CORRECTION_PROMPT_VERSION = "1.0.0"
QUIZ_REWRITE_NATURALLY_PROMPT_VERSION = "1.0.0"
QUIZ_CONVERSATION_PROMPT_VERSION = "1.0.0"
QUIZ_MINI_ESSAY_PROMPT_VERSION = "1.0.0"

# Prompt templates for each quiz mode
QUIZ_RECALL_PROMPT = """Generate a recall-style quiz question based on the learning item.

The learner must recall the phrase/word from memory.

Learning Item:
- Text: {item_text}
- Definition: {item_definition}
- Example: {item_example}

Generate the question in JSON format:
{{
    "prompt_text": "What does [X] mean?",
    "correct_answer": "the meaning of X"
}}

Return valid JSON only."""


QUIZ_FILL_BLANK_PROMPT = """Generate a fill-in-the-blank quiz question based on the learning item.

The learner must fill in the missing word/phrase.

Learning Item:
- Text: {item_text}
- Definition: {item_definition}
- Example: {item_example}

Generate the question in JSON format:
{{
    "prompt_text": "The phrase ___ means: {item_definition}",
    "correct_answer": "{item_text}"
}}

Important: The prompt_text must contain exactly one [blank] marker.
Return valid JSON only."""


QUIZ_MULTIPLE_CHOICE_PROMPT = """Generate a multiple choice quiz question based on the learning item.

Provide the correct answer and 3 plausible distractors.

Learning Item:
- Text: {item_text}
- Definition: {item_definition}
- Example: {item_example}

Generate the question in JSON format:
{{
    "prompt_text": "What does [X] mean?",
    "correct_answer": "the correct meaning",
    "distractors": ["wrong option 1", "wrong option 2", "wrong option 3"]
}}

Important:
- All distractors must be plausible but incorrect
- Distractors must not equal the correct answer (case-insensitive)
- Return exactly 3 distractors
Return valid JSON only."""


QUIZ_ERROR_CORRECTION_PROMPT = """Generate an error correction quiz question based on the learning item.

Create a sentence with a common mistake related to the learning item, then provide the correction.

Learning Item:
- Text: {item_text}
- Definition: {item_definition}
- Common mistake (wrong_form): {wrong_form}
- Correct form: {correct_form}

Generate the question in JSON format:
{{
    "prompt_text": "Find and correct the error: {sentence_with_error}",
    "correct_answer": "{correct_form}"
}}

Important: The prompt_text must contain an error (not equal to correct_answer).
Return valid JSON only."""


QUIZ_REWRITE_NATURALLY_PROMPT = """Generate a rewrite-naturally quiz prompt based on the learning item.

Ask the learner to rewrite an awkward or unnatural sentence to sound more natural.

Learning Item:
- Text: {item_text}
- Definition: {item_definition}
- Example: {item_example}

Generate the prompt in JSON format:
{{
    "prompt_text": "Rewrite this to sound more natural: {unnatural_sentence}",
    "correct_answer": null
}}

Return valid JSON only."""


QUIZ_CONVERSATION_PROMPT = """Generate a conversation starter prompt based on the learning item.

Create a prompt that asks the learner to use the learning item in a conversation.

Learning Item:
- Text: {item_text}
- Definition: {item_definition}
- Example: {item_example}

Generate the prompt in JSON format:
{{
    "prompt_text": "Write a short dialogue (2-3 turns) that naturally uses: {item_text}",
    "correct_answer": null
}}

Return valid JSON only."""


QUIZ_MINI_ESSAY_PROMPT = """Generate a mini-essay prompt based on the learning item.

Create a prompt that asks the learner to write about a topic using the learning item.

Learning Item:
- Text: {item_text}
- Definition: {item_definition}
- Example: {item_example}

Generate the prompt in JSON format:
{{
    "prompt_text": "Write a short paragraph (50-100 words) about [topic] using: {item_text}",
    "correct_answer": null
}}

Return valid JSON only."""


# Mapping from quiz mode to prompt template
QUIZ_PROMPTS = {
    "quiz_recall": QUIZ_RECALL_PROMPT,
    "quiz_fill_blank": QUIZ_FILL_BLANK_PROMPT,
    "quiz_multiple_choice": QUIZ_MULTIPLE_CHOICE_PROMPT,
    "quiz_error_correction": QUIZ_ERROR_CORRECTION_PROMPT,
    "quiz_rewrite_naturally": QUIZ_REWRITE_NATURALLY_PROMPT,
    "quiz_conversation": QUIZ_CONVERSATION_PROMPT,
    "quiz_mini_essay": QUIZ_MINI_ESSAY_PROMPT,
}

# Version constants mapping (ADR-13)
QUIZ_PROMPT_VERSIONS = {
    "quiz_recall": QUIZ_RECALL_PROMPT_VERSION,
    "quiz_fill_blank": QUIZ_FILL_BLANK_PROMPT_VERSION,
    "quiz_multiple_choice": QUIZ_MULTIPLE_CHOICE_PROMPT_VERSION,
    "quiz_error_correction": QUIZ_ERROR_CORRECTION_PROMPT_VERSION,
    "quiz_rewrite_naturally": QUIZ_REWRITE_NATURALLY_PROMPT_VERSION,
    "quiz_conversation": QUIZ_CONVERSATION_PROMPT_VERSION,
    "quiz_mini_essay": QUIZ_MINI_ESSAY_PROMPT_VERSION,
}


def get_quiz_prompt(task: str) -> str:
    """Get the quiz prompt template for a given task.

    Args:
        task: The quiz task identifier (e.g., 'quiz_recall')

    Returns:
        The prompt template string
    """
    return QUIZ_PROMPTS.get(task, "")


def get_quiz_prompt_version(task: str) -> str:
    """Get the version constant for a quiz prompt.

    Args:
        task: The quiz task identifier

    Returns:
        The prompt version string
    """
    return QUIZ_PROMPT_VERSIONS.get(task, "1.0.0")
