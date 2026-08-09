"""Tool definitions for LLM tool-calling (Ollama /api/chat `tools` param).

Corresponds to PRAXIS_CHAT_COACH_PLAN Section 4.1, refactored from the
original forced-JSON `action` field to genuine tool-calling: the model
decides whether to call a tool at all, rather than filling in an
always-present `action` enum on every turn.
"""

from typing import Any

# Version constant (ADR-13 style co-located versioning)
COACH_TOOLS_VERSION = "1.0.0"

START_QUIZ_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "start_quiz",
        "description": (
            "Start a practice quiz for the learner. Only call this when the "
            "learner has clearly asked to practice, review, or quiz themselves "
            "-- never on a greeting or an unrelated message, even if items are "
            "due for review."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "quiz_size": {
                    "type": "integer",
                    "description": "Number of questions, default 10 if unsure.",
                },
            },
            "required": ["quiz_size"],
        },
    },
}

START_WRITING_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "start_writing",
        "description": (
            "Start a writing exercise for the learner. Only call this when the "
            "learner has clearly asked to practice writing or work on a writing "
            "exercise -- never on a greeting or unrelated message."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "writing_topic": {
                    "type": "string",
                    "description": "A topic suggestion relevant to the learner's recent items.",
                },
            },
            "required": ["writing_topic"],
        },
    },
}

# All tools exposed to the coach chat task.
COACH_TOOLS: list[dict[str, Any]] = [START_QUIZ_TOOL, START_WRITING_TOOL]

# Names -> for fast lookup / validation
COACH_TOOL_NAMES: frozenset[str] = frozenset(
    tool["function"]["name"] for tool in COACH_TOOLS
)
