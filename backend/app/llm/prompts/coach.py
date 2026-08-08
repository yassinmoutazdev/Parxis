"""Coach chat prompt templates.

Corresponds to PRAXIS_CHAT_COACH_PLAN Section 4.1.
"""

# Version constant
COACH_CHAT_PROMPT_VERSION = "2.0.0"

# System prompt for coach chat (tool-calling variant).
#
# The model sees `start_quiz` and `start_writing` as genuine, optional tools
# (via the Ollama `tools` param) and is expected to reply with plain
# conversational text on ordinary turns, only invoking a tool when the learner
# clearly asks for it.
COACH_CHAT_SYSTEM_PROMPT = """You are an AI English learning coach having a conversation with a learner.

Respond conversationally, warmly, and helpfully. You have two optional tools
available: start_quiz and start_writing.

Trigger rules (important):
- Only call start_quiz if the learner explicitly asks to practice, review, or be quizzed.
- Only call start_writing if the learner explicitly asks to practice writing or do a writing exercise.
- Do NOT call a tool on a greeting, small talk, or an unrelated question -- respond in plain text instead.
- If the learner already declined an offer earlier in this conversation, do not re-offer it
  unless they bring it up again themselves.
- Never call more than one tool in the same turn.

For a normal conversational turn, just reply in plain text -- do not call a tool."""

# User-turn template: just the running conversation, formatted as chat history
# by the caller and passed as `messages`; this string is kept for backward
# compatibility with callers that still expect a single formattable template.
COACH_CHAT_PROMPT = COACH_CHAT_SYSTEM_PROMPT

# Lightweight prompt used only to generate a short thread title after the
# first assistant reply in a new thread. Kept separate from the main
# conversational turn now that replies are plain text, not JSON.
COACH_THREAD_TITLE_PROMPT = """Suggest a short chat title based on the learner's own message below.
The title must reflect what THIS learner specifically said, not a generic
description of an English-learning app.

Learner: {user_message}
Coach: {assistant_reply}

Rules:
- Base the title primarily on the learner's message. The coach's reply is
  context only, don't let it dominate the title.
- If the learner's message is just a greeting or small talk with no specific
  topic (e.g. "hi", "hello", "hey there"), use a plain title like "New chat"
  or "Quick hello" -- do NOT invent a generic learning-themed title like
  "English Learning Journey" or "English Practice Introduction".
- 3-6 words, no trailing punctuation.

Generate your response in JSON format:
{{
    "title": "3-6 word title"
}}

Return valid JSON only."""

# Prompt for continuing conversation after quiz completion
COACH_CHAT_AFTER_QUIZ_PROMPT = """The learner just completed a quiz session. Generate ONE comprehensive follow-up message.

Quiz Results:
- Score: {correct}/{total} ({score_pct}%)

Question-by-question breakdown:
{all_questions_formatted}

Focus areas (by error frequency):
{focus_areas_formatted}

Conversation so far:
{messages}

Generate a single message that:
1. Opens with the score and a brief encouraging tone
2. Walks through each question concisely: question type, what was asked, their answer vs correct, why it was right/wrong
3. Identifies 2-3 key focus areas from the patterns above
4. Ends with a specific, actionable suggestion (e.g., "Want to practice PHRASAL_VERB items?" or "Try a FILL_BLANK quiz on COLLOCATIONs")
5. Invites them to ask about any question

Style: Conversational, supportive, like a tutor reviewing a worksheet. Not robotic.

Generate your response in JSON format:
{{
    "reply_text": "Your comprehensive follow-up message"
}}

Return valid JSON only."""

# Prompt for continuing conversation after writing submission
COACH_CHAT_AFTER_WRITING_PROMPT = """The learner just completed a writing exercise.

Writing topic: {topic}
Word count: {word_count}

Key feedback points from evaluation:
{feedback_points}

Provide a brief, encouraging follow-up message that:
1. Acknowledges their effort
2. Highlights one specific thing they did well, or one specific correction
   from the feedback above, referencing it concretely -- don't invent details
   not present in the feedback
3. Suggests one area to focus on, grounded in the feedback above

Conversation so far:
{messages}

Generate your response in JSON format:
{{
    "reply_text": "Your follow-up message"
}}

Return valid JSON only."""
