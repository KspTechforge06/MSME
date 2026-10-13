"""Local model access through Ollama.

The model's only job is to read unstructured text and propose candidate facts
with supporting quotes and uncertainty notes. It never performs arithmetic and
never decides a finding; that is left to ``validate.py``.
"""
from __future__ import annotations

import json
from typing import Any

import requests

from config import MAX_TEXT_CHARS, MODEL, OLLAMA_HOST
from parsing import parse_number, to_iso_date
from schema import DOC_TYPES, NUMBER_FIELDS, DocumentFacts


class OllamaUnavailable(RuntimeError):
    """Raised when the local Ollama service cannot be reached or errors out."""


# NOTE: every field is a plain string on purpose. Nullable union types
# (e.g. ["string", "null"]) make Ollama's JSON-schema grammar loop indefinitely
# with qwen2.5:3b, so absent values are expressed as an empty string and
# normalised to None in Python instead.
FACT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "document_type": {"type": "string", "enum": DOC_TYPES},
        "document_number": {"type": "string"},
        "buyer": {"type": "string"},
        "supplier": {"type": "string"},
        "currency": {"type": "string"},
        "amount": {"type": "string"},
        "issue_date": {"type": "string"},
        "due_date": {"type": "string"},
        "delivery_date": {"type": "string"},
        "quantity": {"type": "string"},
        "payment_amount": {"type": "string"},
        "payment_date": {"type": "string"},
        "source_quotes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string"},
                    "quote": {"type": "string"},
                },
                "required": ["field", "quote"],
            },
        },
        "uncertainties": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "document_type",
        "document_number",
        "buyer",
        "supplier",
        "currency",
        "amount",
        "issue_date",
        "due_date",
        "delivery_date",
        "quantity",
        "payment_amount",
        "payment_date",
        "source_quotes",
        "uncertainties",
    ],
}

SYSTEM_PROMPT = """You extract facts from a single business document.

Rules:
- Use ONLY information that appears in the document. Never invent values.
- Classify by document structure, not by numbers it mentions. A message with
  "From:", "To:" and "Subject:" lines is an "email", even when it quotes an
  invoice number or amount. Leave "amount" empty for emails unless the message
  itself is a bill; do not copy a quoted invoice total into an email's amount.
- If a field is not present or is ambiguous, set it to an empty string "" and add
  a short note to "uncertainties". Do not guess.
- Write numbers as plain digits without currency symbols, spaces or commas
  (for example "48000"). Never write "INR 48,000".
- Copy short verbatim quotes into "source_quotes" for every value you report,
  using the field name and the exact text it came from.
- "currency" is the currency shown on the document, e.g. "INR", "USD".
- "quantity" is the number of units/items, written as digits only.
- Dates must be written as YYYY-MM-DD when the document allows it.
- "amount" is the document's total/face amount for the transaction. For a
  payment ledger, leave "amount" empty and use "payment_amount"/"payment_date".
- Return only JSON that matches the provided schema."""


def _post_chat(payload: dict[str, Any], timeout: int = 180) -> dict[str, Any]:
    try:
        response = requests.post(f"{OLLAMA_HOST}/api/chat", json=payload, timeout=timeout)
    except requests.RequestException as exc:  # connection refused, timeout, ...
        raise OllamaUnavailable(
            f"Could not reach Ollama at {OLLAMA_HOST}. Is the service running?"
        ) from exc
    if response.status_code >= 400:
        raise OllamaUnavailable(
            f"Ollama returned HTTP {response.status_code}: {response.text[:200]}"
        )
    return response.json()


def check_available() -> bool:
    """True when the local Ollama API answers."""
    try:
        return requests.get(f"{OLLAMA_HOST}/api/tags", timeout=3).ok
    except requests.RequestException:
        return False


def list_models() -> list[str]:
    """Names of locally installed models, or an empty list when unreachable."""
    try:
        payload = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5).json()
    except (requests.RequestException, ValueError):
        return []
    return [entry.get("name", "") for entry in payload.get("models", [])]


def _chat(text: str, filename: str, use_schema: bool) -> str:
    user_prompt = (
        f"Document filename: {filename}\n\n"
        "Document text (between the markers):\n"
        "<<<DOCUMENT\n"
        f"{text[:MAX_TEXT_CHARS]}\n"
        "DOCUMENT>>>\n\n"
        "Return the extracted facts as JSON."
    )
    payload: dict[str, Any] = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {"temperature": 0},
    }
    payload["format"] = FACT_SCHEMA if use_schema else "json"
    data = _post_chat(payload)
    return data.get("message", {}).get("content", "") or ""


def _parse_json(content: str) -> dict[str, Any]:
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.lower().startswith("json"):
            content = content[4:]
    return json.loads(content)


def _normalise(raw: dict[str, Any]) -> dict[str, Any]:
    document_type = str(raw.get("document_type") or "unknown").strip().lower()
    if document_type not in DOC_TYPES:
        document_type = "unknown"

    cleaned: dict[str, Any] = {"document_type": document_type}
    for field in (
        "document_number",
        "buyer",
        "supplier",
        "currency",
        "issue_date",
        "due_date",
        "delivery_date",
        "payment_date",
    ):
        value = raw.get(field)
        if value is None:
            cleaned[field] = None
        elif field.endswith("_date"):
            cleaned[field] = to_iso_date(value)
        else:
            text = str(value).strip()
            cleaned[field] = text or None

    for field in NUMBER_FIELDS:
        cleaned[field] = parse_number(raw.get(field))

    quotes = raw.get("source_quotes") or []
    cleaned["source_quotes"] = [
        {"field": str(q.get("field", "")), "quote": str(q.get("quote", ""))}
        for q in quotes
        if isinstance(q, dict) and q.get("quote")
    ]
    uncertainties = raw.get("uncertainties") or []
    cleaned["uncertainties"] = [str(u) for u in uncertainties if str(u).strip()]
    return cleaned


def extract_facts(filename: str, text: str) -> DocumentFacts:
    """Extract structured facts for one document using the local model."""
    facts = DocumentFacts(filename=filename, text_excerpt=text[:2000])
    try:
        content = _chat(text, filename, use_schema=True)
        raw = _parse_json(content)
    except (json.JSONDecodeError, KeyError):
        # Some model/grammar combinations occasionally emit unfenced text; retry
        # once in plain JSON mode before giving up.
        content = _chat(text, filename, use_schema=False)
        raw = _parse_json(content)

    for key, value in _normalise(raw).items():
        setattr(facts, key, value)
    return facts


def extract_all(documents: list[tuple[str, str]]) -> list[DocumentFacts]:
    """Extract facts for many ``(filename, text)`` pairs."""
    return [extract_facts(name, text) for name, text in documents]
