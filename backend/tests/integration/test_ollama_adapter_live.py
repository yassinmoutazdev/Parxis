"""Integration test for OllamaAdapter.

Corresponds to ARCHITECTURE Section 17.2 (Testing Boundaries).

This test is intentionally NOT mocked - it runs against a real Ollama instance
when available. Use pytest.mark.skipif to skip when OLLAMA_HOST is unreachable.
"""

import pytest

from app.config import settings
from app.llm.ollama_adapter import OllamaAdapter
from app.llm.schemas import ParsedNoteOutput


def is_ollama_reachable() -> bool:
    """Check if Ollama is reachable at the configured host.

    Returns:
        True if Ollama is reachable AND has the configured model, False otherwise
    """
    import httpx

    try:
        # First check if Ollama API is reachable
        response = httpx.get(f"{settings.ollama_host}/api/tags", timeout=5.0)
        if response.status_code != 200:
            return False

        # Then check if the configured model is available
        models = response.json().get("models", [])
        model_names = [m.get("name", "") for m in models]
        has_model = any(settings.ollama_model in name for name in model_names)

        return has_model
    except Exception:
        return False


# Skip this test suite if Ollama is not available
pytestmark = pytest.mark.skipif(
    not is_ollama_reachable(),
    reason="OLLAMA_HOST is not reachable",
)


class TestOllamaAdapterLive:
    """Live integration tests for OllamaAdapter.

    These tests require a running Ollama instance and will be skipped
    if the host is unreachable.
    """

    @pytest.fixture
    def adapter(self) -> OllamaAdapter:
        """Create an OllamaAdapter instance."""
        return OllamaAdapter()

    @pytest.mark.asyncio
    async def test_parse_note_roundtrip(self, adapter: OllamaAdapter):
        """Test that parse_note task round-trips correctly.

        This validates that:
        1. The adapter can connect to Ollama
        2. Schema-constrained output works
        3. The response can be parsed into the expected schema

        Per ARCHITECTURE Section 11.1, this is the one suite intentionally
        NOT mocked to validate ADR-06's real-world assumption.
        """
        # Arrange
        context = {
            "note_content": "Break the ice means to initiate conversation. Example: Let me break the ice at the party.",
            "recent_item_texts": [],
        }

        # Act
        result = await adapter.generate(
            task="parse_note",
            context=context,
            output_schema=ParsedNoteOutput,
        )

        # Assert
        assert isinstance(result, ParsedNoteOutput)
        assert len(result.items) > 0
        # Verify at least one item has a valid source_excerpt
        items_with_source = [i for i in result.items if i.source_excerpt]
        assert len(items_with_source) > 0

    @pytest.mark.asyncio
    async def test_generate_returns_valid_schema(self, adapter: OllamaAdapter):
        """Test that generate returns valid schema-constrained output."""
        context = {
            "note_content": "Learn idioms: break the ice, hit the nail on the head.",
            "recent_item_texts": [],
        }

        result = await adapter.generate(
            task="parse_note",
            context=context,
            output_schema=ParsedNoteOutput,
        )

        # Verify the output can be serialized back to JSON
        json_data = result.model_dump_json()
        assert json_data

        # Verify it validates again after dump
        reparsed = ParsedNoteOutput.model_validate_json(json_data)
        assert reparsed.items is not None