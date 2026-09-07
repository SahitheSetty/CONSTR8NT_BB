import numpy as np
import pytest

from blackbox_engine.exporter import confidence_bucket, export_investigation
from blackbox_engine.mocks import FlakyMock, ScenarioMock
from blackbox_engine.orchestrator import Investigation
from blackbox_engine.spec_loader import Hypothesis, Likelihood, Spec


def _four_hypothesis_spec() -> Spec:
    hypotheses = ["h0", "h1", "h2", "h3"]
    table = {
        "open": {"h0": 0.9, "h1": 0.6, "h2": 0.3, "h3": 0.1},
        "refused": {"h0": 0.1, "h1": 0.4, "h2": 0.7, "h3": 0.9},
    }
    hyp_objects = {
        h: Hypothesis(key=h, prior=0.25, label=f"label-{h}", remediation=f"remediation-{h}")
        for h in hypotheses
    }
    return Spec(
        hypotheses=hyp_objects,
        likelihoods={"tcp_443": Likelihood("tcp_443", cost_seconds=0.5, table=table)},
    )


async def _run(spec: Spec, probe_runner, **kwargs) -> list:
    investigation = Investigation("example.com", spec, probe_runner, **kwargs)
    return [event async for event in investigation.run()]


async def test_export_matches_the_frontend_contract_shape():
    spec = _four_hypothesis_spec()
    mock = ScenarioMock({"tcp_443": "open"}, latency_ms=0.0)
    events = await _run(spec, mock, budget_s=10.0, threshold=0.99)

    payload = export_investigation(events, spec)

    assert set(payload) == {"diagnosis", "hypotheses", "evidence", "reasoningTrace"}
    assert set(payload["diagnosis"]) == {
        "probableCause",
        "confidence",
        "supportingEvidence",
        "alternativeHypotheses",
    }
    for item in payload["hypotheses"]:
        assert set(item) == {"hypothesis", "confidence", "reason"}
    for statement in payload["evidence"]:
        assert isinstance(statement, str)


async def test_export_computes_expected_values_for_a_known_scenario():
    spec = _four_hypothesis_spec()
    mock = ScenarioMock({"tcp_443": "open"}, latency_ms=0.0)
    events = await _run(spec, mock, budget_s=10.0, threshold=0.99)

    payload = export_investigation(events, spec)

    # posterior after observing "open" from a uniform 0.25 prior:
    # h0=0.9*.25=.225 h1=0.6*.25=.15 h2=0.3*.25=.075 h3=0.1*.25=.025 -> sum .475
    # normalised: h0=.4737 h1=.3158 h2=.1579 h3=.0526
    assert payload["diagnosis"]["probableCause"] == "label-h0"
    assert payload["diagnosis"]["confidence"] == "low"  # 0.4737 < 0.55
    assert payload["diagnosis"]["supportingEvidence"] == ['tcp_443 was observed as "open".']
    assert payload["diagnosis"]["alternativeHypotheses"] == ["label-h1", "label-h2", "label-h3"]

    assert payload["evidence"] == ['tcp_443 was observed as "open".']

    hyps = payload["hypotheses"]
    assert [h["hypothesis"] for h in hyps] == ["label-h0", "label-h1", "label-h2", "label-h3"]
    assert [h["reason"] for h in hyps] == [
        "remediation-h0",
        "remediation-h1",
        "remediation-h2",
        "remediation-h3",
    ]
    assert hyps[0]["confidence"] == "low"  # 0.4737
    assert hyps[1]["confidence"] == "low"  # 0.3158
    assert hyps[2]["confidence"] == "low"  # 0.1579
    assert hyps[3]["confidence"] == "low"  # 0.0526

    trace = payload["reasoningTrace"]
    assert len(trace) == 1
    step = trace[0]
    assert step["probe"] == "tcp_443"
    assert step["chose_over"] == []
    assert step["symbol"] == "open"
    assert step["measured"] is True
    assert step["belief_before"] == pytest.approx({"h0": 0.25, "h1": 0.25, "h2": 0.25, "h3": 0.25})
    assert step["belief_after"]["h0"] == pytest.approx(0.47368421, abs=1e-6)
    assert step["entropy_before"] == pytest.approx(2.0)  # log2(4)
    assert step["entropy_after"] < step["entropy_before"]


async def test_export_records_unmeasured_step_without_changing_belief():
    spec = _four_hypothesis_spec()
    inner = ScenarioMock({"tcp_443": "open"}, latency_ms=0.0)
    flaky = FlakyMock(inner, failure_rate=1.0, rng=np.random.default_rng(0))
    events = await _run(spec, flaky, budget_s=10.0, threshold=0.99)

    payload = export_investigation(events, spec)

    assert payload["evidence"] == ["tcp_443 could not be measured (FlakyMock injected a failure "
                                    "(failure_rate=1.0))."]
    assert payload["diagnosis"]["confidence"] == "low"
    # all four hypotheses are exactly tied at the uniform prior (no evidence
    # ever updated beliefs), so any of them is a valid "top" pick -- the
    # point of this test is that belief didn't change, not which tied
    # hypothesis argsort happens to pick.
    assert payload["diagnosis"]["probableCause"] in {"label-h0", "label-h1", "label-h2", "label-h3"}

    step = payload["reasoningTrace"][0]
    assert step["measured"] is False
    assert step["symbol"] is None
    assert step["belief_before"] == step["belief_after"]
    assert step["entropy_before"] == step["entropy_after"]


async def test_export_raises_if_events_do_not_end_in_a_verdict():
    spec = _four_hypothesis_spec()
    mock = ScenarioMock({"tcp_443": "open"}, latency_ms=0.0)
    events = await _run(spec, mock, budget_s=10.0, threshold=0.99)

    with pytest.raises(ValueError, match="Verdict"):
        export_investigation(events[:-1], spec)


@pytest.mark.parametrize(
    ("probability", "expected"),
    [
        (1.0, "high"),
        (0.80, "high"),
        (0.7999999, "medium"),
        (0.55, "medium"),
        (0.5499999, "low"),
        (0.0, "low"),
    ],
)
def test_confidence_bucket_boundaries(probability, expected):
    assert confidence_bucket(probability) == expected
