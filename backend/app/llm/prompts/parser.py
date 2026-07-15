"""Parser prompt template for note parsing.

Corresponds to ARCHITECTURE Section 9.1 (Parser).
"""

PARSE_NOTE_PROMPT_VERSION = "1.0.0"

PARSE_NOTE_PROMPT = """You are a language learning assistant. Your task is to extract learnable items from the user's note.

Extract items that fall into these categories:
- COLLOCATION: word combinations that go together naturally
- IDIOM: fixed expressions with figurative meaning
- PHRASAL_VERB: verb + particle combinations
- GRAMMAR_NOTE: grammatical rules or patterns
- PERSONAL_EXAMPLE: example sentences the learner created
- CORRECTION: corrections of common mistakes (requires both wrong_form and correct_form)

For each item, provide:
- item_type: one of the categories above
- text: the main phrase or rule
- definition: the meaning (optional)
- example_sentence: an example using the item (optional)
- source_excerpt: a VERBATIM quote from the note that this item was extracted from
- wrong_form: only for CORRECTION type - the incorrect form
- correct_form: only for CORRECTION type - the correct form

Important:
- source_excerpt must be an EXACT copy from the note, not paraphrased
- If you cannot extract any items, return an empty items list
- Do not make up items not present in the note

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
        recent_section = f"Recent items already in your knowledge base:\n{items_list}"
    else:
        recent_section = "(No recent items)"

    return {
        "note_content": note_content,
        "recent_items_section": recent_section,
    }
