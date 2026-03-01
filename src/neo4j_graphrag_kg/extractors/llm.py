"""LLM-powered entity and relationship extractor.

Supports Anthropic (Claude) and OpenAI (GPT) via their respective SDKs.
SDKs are imported lazily — the base package works without them installed.

NEVER logs or prints API keys.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from neo4j_graphrag_kg.extractors.base import (
    BaseExtractor,
    ExtractedEntity,
    ExtractedRelationship,
    ExtractionResult,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default schema constraints
# ---------------------------------------------------------------------------
DEFAULT_ENTITY_TYPES = [
    "Person", "Organization", "Location", "Technology", "Concept",
]
DEFAULT_RELATIONSHIP_TYPES = [
    "WORKS_FOR", "LOCATED_IN", "RELATED_TO", "USES", "PART_OF",
]

# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = """\
You are an expert knowledge-graph builder. Given a text chunk, extract \
all meaningful entities and relationships.

Return ONLY a JSON object (no markdown fences, no explanation) with this \
exact structure:

{{
  "entities": [
    {{"name": "...", "type": "...", "evidence": "..."}}
  ],
  "relationships": [
    {{"source": "...", "target": "...", "type": "...", "confidence": 0.0, "evidence": "..."}}
  ]
}}

Rules:
- Entity names should be capitalised properly (e.g. "Neo4j", "Alice Smith").
- Entity types MUST be one of: {entity_types}.
- Relationship types MUST be one of: {relationship_types}.
- confidence is a float between 0.0 and 1.0.
- evidence is a short phrase from the source text supporting the extraction.
- De-duplicate: do not repeat the same entity or relationship.
- If no entities or relationships are found, return empty lists.
"""

_USER_PROMPT = "Extract entities and relationships from this text:\n\n{text}"


# ---------------------------------------------------------------------------
# JSON parsing helpers
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?\s*```", re.DOTALL)


def _parse_json_response(raw: str) -> dict[str, Any]:
    """Parse a JSON response, handling markdown fences and minor issues."""
    text = raw.strip()

    # Strip markdown code fences if present
    m = _FENCE_RE.search(text)
    if m:
        text = m.group(1).strip()

    # Try parsing directly
    try:
        return json.loads(text)  # type: ignore[no-any-return]
    except json.JSONDecodeError:
        pass

    # Try to find the first { ... } block
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse JSON from LLM response: {text[:200]}...")


def _safe_float(val: Any) -> float:
    """Coerce a value to float, defaulting to 1.0."""
    try:
        f = float(val)
        return max(0.0, min(1.0, f))
    except (TypeError, ValueError):
        return 1.0


# ---------------------------------------------------------------------------
# Provider-specific call wrappers
# ---------------------------------------------------------------------------

def _call_anthropic(
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
) -> str:
    """Call the Anthropic Messages API. Returns the text response."""
    try:
        import anthropic
    except ImportError:
        raise ImportError(
            "The 'anthropic' package is required for the LLM extractor with "
            "provider='anthropic'. Install it with: pip install -e \".[anthropic]\""
        )

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=4096,
        temperature=0,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    # Extract text from content blocks
    return "".join(
        block.text for block in message.content if hasattr(block, "text")
    )


def _call_openai(
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
) -> str:
    """Call the OpenAI ChatCompletion API. Returns the text response."""
    try:
        import openai
    except ImportError:
        raise ImportError(
            "The 'openai' package is required for the LLM extractor with "
            "provider='openai'. Install it with: pip install -e \".[openai]\""
        )

    client = openai.OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content or ""


_PROVIDERS: dict[str, callable] = {
    "anthropic": _call_anthropic,
    "openai": _call_openai,
}


# ---------------------------------------------------------------------------
# LLMExtractor
# ---------------------------------------------------------------------------

class LLMExtractor(BaseExtractor):
    """LLM-powered extractor supporting Anthropic and OpenAI providers.

    Parameters
    ----------
    provider:
        ``"anthropic"`` or ``"openai"``.
    model:
        Model name (e.g. ``"claude-sonnet-4-20250514"``, ``"gpt-4o"``).
    api_key:
        API key. **Never** logged or printed.
    entity_types:
        Allowed entity type labels (constrains the LLM output).
    relationship_types:
        Allowed relationship type labels.
    max_retries:
        Maximum number of retry attempts on API or parse failure.
    """

    def __init__(
        self,
        *,
        provider: str = "anthropic",
        model: str | None = None,
        api_key: str = "",
        entity_types: list[str] | None = None,
        relationship_types: list[str] | None = None,
        max_retries: int = 1,
    ) -> None:
        if provider not in _PROVIDERS:
            raise ValueError(
                f"Unsupported LLM provider {provider!r}. "
                f"Choose from: {', '.join(_PROVIDERS)}"
            )
        if not api_key:
            raise ValueError(
                "LLM_API_KEY is required for the LLM extractor. "
                "Set it in .env or pass --api-key."
            )

        self._provider = provider
        self._model = model or (
            "claude-sonnet-4-20250514" if provider == "anthropic" else "gpt-4o"
        )
        self._api_key = api_key
        self._entity_types = entity_types or DEFAULT_ENTITY_TYPES
        self._relationship_types = relationship_types or DEFAULT_RELATIONSHIP_TYPES
        self._max_retries = max_retries
        self._call_fn = _PROVIDERS[provider]

        # Log config (NEVER the key)
        logger.info(
            "LLMExtractor initialised: provider=%s model=%s entity_types=%s",
            self._provider,
            self._model,
            self._entity_types,
        )

    # ---- Build prompts ---------------------------------------------------

    def _build_system_prompt(self) -> str:
        return _SYSTEM_PROMPT.format(
            entity_types=", ".join(self._entity_types),
            relationship_types=", ".join(self._relationship_types),
        )

    # ---- API call with retry ---------------------------------------------

    def _call_llm(self, text: str) -> str:
        """Call the LLM with retry logic. Returns raw text response."""
        system = self._build_system_prompt()
        user = _USER_PROMPT.format(text=text)
        last_error: Exception | None = None

        for attempt in range(1 + self._max_retries):
            try:
                t0 = time.perf_counter()
                response = self._call_fn(
                    self._api_key, self._model, system, user,
                )
                elapsed = time.perf_counter() - t0
                logger.debug(
                    "LLM call took %.2fs (attempt %d)", elapsed, attempt + 1,
                )
                return response
            except Exception as exc:
                last_error = exc
                if attempt < self._max_retries:
                    wait = 2 ** attempt
                    logger.warning(
                        "LLM call failed (attempt %d/%d), retrying in %ds: %s",
                        attempt + 1,
                        1 + self._max_retries,
                        wait,
                        type(exc).__name__,
                    )
                    time.sleep(wait)

        raise RuntimeError(
            f"LLM call failed after {1 + self._max_retries} attempts"
        ) from last_error

    # ---- Main extract method ---------------------------------------------

    def extract(
        self,
        text: str,
        chunk_id: str,
        doc_id: str,
    ) -> ExtractionResult:
        """Extract entities and relationships from *text* using the LLM."""
        raw = self._call_llm(text)

        # Parse with one retry on JSON failure
        parsed: dict[str, Any] | None = None
        for parse_attempt in range(2):
            try:
                parsed = _parse_json_response(raw)
                break
            except ValueError:
                if parse_attempt == 0:
                    logger.warning("JSON parse failed, retrying LLM call")
                    raw = self._call_llm(text)

        if parsed is None:
            logger.warning(
                "Could not parse LLM response for chunk %s; returning empty",
                chunk_id,
            )
            return ExtractionResult()

        # Convert to dataclasses
        entities: list[ExtractedEntity] = []
        for ent in parsed.get("entities", []):
            name = str(ent.get("name", "")).strip()
            etype = str(ent.get("type", "Term")).strip()
            if not name:
                continue
            entities.append(ExtractedEntity(
                name=name,
                type=etype,
                properties={"evidence": ent.get("evidence", "")},
            ))

        relationships: list[ExtractedRelationship] = []
        for rel in parsed.get("relationships", []):
            src = str(rel.get("source", "")).strip()
            tgt = str(rel.get("target", "")).strip()
            rtype = str(rel.get("type", "RELATED_TO")).strip()
            if not src or not tgt:
                continue
            relationships.append(ExtractedRelationship(
                source=src,
                target=tgt,
                type=rtype,
                confidence=_safe_float(rel.get("confidence", 1.0)),
                evidence=str(rel.get("evidence", "")),
            ))

        logger.info(
            "LLM extracted %d entities, %d relationships from chunk %s",
            len(entities),
            len(relationships),
            chunk_id,
        )
        return ExtractionResult(entities=entities, relationships=relationships)
