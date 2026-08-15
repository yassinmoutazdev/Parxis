"""Parser prompt template for note parsing.

Corresponds to ARCHITECTURE Section 9.1 (Parser).
Updated per Part E: quality bar, required definition/example_sentence,
confidence field, semantic redundancy self-check.
Updated per Part H: low_confidence_reason (explains *why* the model is
unsure, so it can drive a targeted retry and, for chat-sourced items,
double as the clarifying question asked back to the user).
"""

PARSE_NOTE_PROMPT_VERSION = "2.1.0"

PARSE_NOTE_PROMPT = """You are a language learning assistant. Your task is to extract learnable items from the user's note.

Extract items that fall into these categories:
- COLLOCATION: word combinations that go together naturally (e.g., "make a decision", "heavy rain")
- IDIOM: fixed expressions with figurative meaning (e.g., "break the ice", "piece of cake")
- PHRASAL_VERB: verb + particle combinations (e.g., "give up", "look forward to")
- GRAMMAR_NOTE: grammatical rules or patterns (e.g., "present perfect for experience")
- PERSONAL_EXAMPLE: example sentences the learner created to illustrate a point
- CORRECTION: corrections of common mistakes (requires both wrong_form and correct_form)

QUALITY BAR - SKIP items that are:
- Trivially basic (something an intermediate+ learner obviously already knows: "hello", "thank you", "I am")
- Not a self-contained teachable unit (fragments, single common words without pattern value)
- Already well-represented in the learner's recent items (see recent_items_section below)

For each item, provide:
- item_type: one of the categories above
- text: the main phrase or rule
- definition: the meaning/explanation (REQUIRED for all non-CORRECTION types)
- example_sentence: an example using the item (REQUIRED for all non-CORRECTION types)
- source_excerpt: a VERBATIM quote from the note that this item was extracted from
- wrong_form: only for CORRECTION type - the incorrect form
- correct_form: only for CORRECTION type - the correct form
- confidence: "high" | "medium" | "low" - your self-reported confidence this is a solid, well-formed extraction
- low_confidence_reason: REQUIRED whenever confidence is "low". Explain SPECIFICALLY what you're unsure
  about - e.g. "unclear whether this is meant idiomatically or literally", "ambiguous which sense of
  the word is intended", "uncertain this register (formal/informal) is correct". Do not write a generic
  "not sure" - this text is reused directly to ask the learner a clarifying question, so it needs to name
  the actual ambiguity.
- possible_duplicate_reason: if you suspect semantic overlap with an item in recent_items_section (even if wording differs), explain why; otherwise omit

Important:
- source_excerpt must be an EXACT copy from the note, not paraphrased
- If you cannot extract any items meeting the quality bar, return an empty items list
- Do not make up items not present in the note
- For CORRECTION type: definition and example_sentence are optional; wrong_form and correct_form are REQUIRED

Note content:
{note_content}

{recent_items_section}

Extract the items now."""


def get_parse_note_prompt() -> str:
    """Get the parse_note prompt template.

    Returns:
        The prompt template string
    """
    return PARSE_NOTE_PROMPT


def build_parse_note_context(note_content: str, recent_item_texts: list[str] | None = None) -> dict:
    """Build context dict for parse_note prompt.

    Args:
        note_content: The raw markdown note content
        recent_item_texts: List of recent learning item texts

    Returns:
        Context dict for prompt formatting
    """
    if recent_item_texts:
        items_list = "\n".join(f"- {text}" for text in recent_item_texts[:50])
        recent_section = f"Recent items already in your knowledge base (check for semantic redundancy):\n{items_list}"
    else:
        recent_section = "(No recent items)"

    return {
        "note_content": note_content,
        "recent_items_section": recent_section,
    }
