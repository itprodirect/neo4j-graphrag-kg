"""RAG answer generation: query results → natural language answer.

Takes the original question, generated Cypher, and query results,
then uses the LLM to produce a grounded natural language answer.

NEVER logs or prints API keys.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Response container
# ---------------------------------------------------------------------------

@dataclass
class RAGResponse:
    """Result of a RAG query pipeline invocation."""

    question: str
    cypher: str
    results: list[dict[str, Any]] = field(default_factory=list)
    answer: str = ""
    elapsed_s: float = 0.0


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a knowledge graph assistant. Answer the question using ONLY the \
provided query results. If the results are empty or insufficient, say so \
clearly. Be concise and factual.
"""

_USER_PROMPT = """\
Question: {question}

Cypher query used:
{cypher}

Query results (as rows):
{results}

Based on these results, answer the question concisely."""


# ---------------------------------------------------------------------------
# Provider call wrappers (identical to text2cypher — kept separate to
# avoid cross-module coupling on internal implementation details)
# ---------------------------------------------------------------------------

def _call_anthropic(api_key: str, model: str, system: str, user: str) -> str:
    try:
        import anthropic
    except ImportError:
        raise ImportError(
            "The 'anthropic' package is required for RAG answers. "
            "Install it with: pip install -e \".[anthropic]\""
        )
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=2048,
        temperature=0,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(
        block.text for block in message.content if hasattr(block, "text")
    )


def _call_openai(api_key: str, model: str, system: str, user: str) -> str:
    try:
        import openai
    except ImportError:
        raise ImportError(
            "The 'openai' package is required for RAG answers. "
            "Install it with: pip install -e \".[openai]\""
        )
    client = openai.OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return response.choices[0].message.content or ""


_PROVIDERS: dict[str, Any] = {
    "anthropic": _call_anthropic,
    "openai": _call_openai,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _format_results(rows: list[dict[str, Any]], max_rows: int = 50) -> str:
    """Format query result rows as a readable string for the LLM."""
    if not rows:
        return "(no results)"
    truncated = rows[:max_rows]
    lines = []
    for i, row in enumerate(truncated, 1):
        parts = [f"{k}: {v}" for k, v in row.items()]
        lines.append(f"  Row {i}: {', '.join(parts)}")
    text = "\n".join(lines)
    if len(rows) > max_rows:
        text += f"\n  ... ({len(rows) - max_rows} more rows truncated)"
    return text


def generate_answer(
    question: str,
    cypher: str,
    results: list[dict[str, Any]],
    *,
    provider: str = "anthropic",
    model: str = "",
    api_key: str = "",
) -> str:
    """Generate a natural language answer from query results.

    Returns the answer string.
    """
    if not api_key:
        raise ValueError(
            "LLM_API_KEY is required for RAG answer generation. "
            "Set it in .env or as an environment variable."
        )
    if provider not in _PROVIDERS:
        raise ValueError(
            f"Unsupported LLM provider {provider!r}. "
            f"Choose from: {', '.join(_PROVIDERS)}"
        )

    resolved_model = model or (
        "claude-sonnet-4-20250514" if provider == "anthropic" else "gpt-4o"
    )
    call_fn = _PROVIDERS[provider]

    formatted_results = _format_results(results)
    user = _USER_PROMPT.format(
        question=question,
        cypher=cypher,
        results=formatted_results,
    )

    t0 = time.perf_counter()
    answer = call_fn(api_key, resolved_model, _SYSTEM_PROMPT, user)
    elapsed = time.perf_counter() - t0
    logger.info("Answer generation LLM call took %.2fs", elapsed)

    return answer.strip()
