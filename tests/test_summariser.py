import json
import urllib.error
from unittest.mock import MagicMock

import pytest

from blackbox_engine.summariser import summarise

_EXPORT_JSON = {
    "diagnosis": {
        "probableCause": "DNS authoritative nameserver down",
        "confidence": "high",
        "supportingEvidence": [
            'dns_resolution was observed as "servfail".',
            'dns_consistency was observed as "auth_differs_from_cache".',
        ],
        "alternativeHypotheses": ["DNS failure"],
    },
    "hypotheses": [
        {"hypothesis": "DNS authoritative nameserver down", "confidence": "high", "reason": "n/a"},
    ],
    "evidence": [
        'dns_resolution was observed as "servfail".',
        'dns_consistency was observed as "auth_differs_from_cache".',
    ],
    "reasoningTrace": [],
}


@pytest.fixture(autouse=True)
def _no_api_key_by_default(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def _fake_urlopen(response_body: dict) -> MagicMock:
    response = MagicMock()
    response.read.return_value = json.dumps(response_body).encode("utf-8")
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    return MagicMock(return_value=response)


def test_defaults_to_template_when_no_api_key():
    result = summarise(_EXPORT_JSON)

    assert "DNS authoritative nameserver down" in result
    assert "high" in result
    assert 'dns_resolution was observed as "servfail".' in result


def test_template_mentions_no_evidence_when_none_recorded():
    export_json = {
        "diagnosis": {
            "probableCause": "server down",
            "confidence": "low",
            "supportingEvidence": [],
            "alternativeHypotheses": [],
        }
    }

    result = summarise(export_json)

    assert "No supporting evidence was recorded" in result


def test_uses_api_backend_when_key_present_and_reachable(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(
        "blackbox_engine.summariser.urllib.request.urlopen",
        _fake_urlopen({"content": [{"type": "text", "text": "The DNS nameserver is down. Fix it."}]}),
    )

    result = summarise(_EXPORT_JSON)

    assert result == "The DNS nameserver is down. Fix it."


def test_api_receives_exactly_the_export_json_and_nothing_else(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    captured_request = {}

    def _capturing_urlopen(request, timeout):
        captured_request["payload"] = json.loads(request.data)
        response = MagicMock()
        response.read.return_value = json.dumps(
            {"content": [{"type": "text", "text": "ok"}]}
        ).encode("utf-8")
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        return response

    monkeypatch.setattr("blackbox_engine.summariser.urllib.request.urlopen", _capturing_urlopen)

    summarise(_EXPORT_JSON)

    sent_content = json.loads(captured_request["payload"]["messages"][0]["content"])
    assert sent_content == _EXPORT_JSON


def test_falls_back_to_template_on_network_error(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    def _raise_network_error(request, timeout):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("blackbox_engine.summariser.urllib.request.urlopen", _raise_network_error)

    result = summarise(_EXPORT_JSON)

    assert "DNS authoritative nameserver down" in result


def test_falls_back_to_template_on_malformed_api_response(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(
        "blackbox_engine.summariser.urllib.request.urlopen",
        _fake_urlopen({"unexpected_shape": True}),
    )

    result = summarise(_EXPORT_JSON)

    assert "DNS authoritative nameserver down" in result


def test_falls_back_to_template_on_empty_api_response(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(
        "blackbox_engine.summariser.urllib.request.urlopen",
        _fake_urlopen({"content": [{"type": "text", "text": "   "}]}),
    )

    result = summarise(_EXPORT_JSON)

    assert "DNS authoritative nameserver down" in result
