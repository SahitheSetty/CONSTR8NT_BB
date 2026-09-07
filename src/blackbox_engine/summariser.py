"""Plain-English prose summary of a finished diagnosis, from JSON only.

Two backends, selected automatically:
- API backend: sends only the finished export JSON to an LLM and asks it
  to summarise it in two sentences. Used when ANTHROPIC_API_KEY is set.
- Template backend: pure f-strings, no network. This is the default, and
  the only backend guaranteed to work offline mid-demo -- any missing
  key, network failure, or malformed API response falls straight back to
  it rather than surfacing an error to the demo.

The LLM is handed nothing but the already-finished export JSON (the exact
dict `exporter.export_investigation` produces) and makes zero diagnostic
decisions -- it prose-summarises a verdict that is already fully decided.
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

_API_URL = "https://api.anthropic.com/v1/messages"
_API_MODEL = "claude-sonnet-5"
_API_VERSION = "2023-06-01"
_API_TIMEOUT_S = 8.0
_MAX_TOKENS = 200

_SYSTEM_PROMPT = (
    "You summarise a finished network-fault diagnosis for a non-technical "
    "reader in exactly two sentences of plain English. You are given only "
    "the finished diagnosis JSON, never raw probe data, and you make no "
    "diagnostic decisions of your own -- state the given probable cause, "
    "its confidence, and one supporting piece of evidence, nothing more."
)


def _template_summary(export_json: dict[str, Any]) -> str:
    diagnosis = export_json["diagnosis"]
    cause = diagnosis["probableCause"]
    confidence = diagnosis["confidence"]
    evidence = diagnosis.get("supportingEvidence") or []

    first_sentence = f"The probable cause is {cause}, with {confidence} confidence."
    second_sentence = (
        f"This is supported by: {evidence[0]}"
        if evidence
        else "No supporting evidence was recorded for this verdict."
    )
    return f"{first_sentence} {second_sentence}"


def _api_summary(export_json: dict[str, Any], api_key: str) -> str:
    payload = json.dumps(
        {
            "model": _API_MODEL,
            "max_tokens": _MAX_TOKENS,
            "system": _SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": json.dumps(export_json)}],
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        _API_URL,
        data=payload,
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": _API_VERSION,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=_API_TIMEOUT_S) as response:
        body = json.loads(response.read())

    text = "".join(block["text"] for block in body["content"] if block["type"] == "text")
    return text.strip()


def summarise(export_json: dict[str, Any]) -> str:
    """Produce two sentences of plain-English explanation of a finished diagnosis.

    `export_json` must be the dict `exporter.export_investigation` produces
    (needs at least `diagnosis.probableCause` and `diagnosis.confidence`).
    Uses the API backend when ANTHROPIC_API_KEY is set; falls back to the
    offline template on a missing key, or on any network failure or
    malformed API response, so a flaky connection never blocks a demo.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return _template_summary(export_json)

    try:
        summary = _api_summary(export_json, api_key)
        if not summary:
            raise ValueError("API returned an empty summary")
        return summary
    except (OSError, KeyError, ValueError):
        return _template_summary(export_json)
