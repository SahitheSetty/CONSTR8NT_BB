"""Loads and validates the hypothesis/likelihood spec (hypotheses.yaml).

This is the second contract boundary in the engine (after adapter.py): a
hand-filled YAML file, not code, is what actually encodes the diagnostic
reasoning. A malformed spec must fail loudly at load time, naming the exact
probe/observation/hypothesis at fault, rather than silently producing a
broken posterior three steps later.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from blackbox_engine.symbols import OBSERVATION_SPACE

_PROBABILITY_MIN = 0.01
_PROBABILITY_MAX = 0.99
_SUM_TOLERANCE = 1e-6


@dataclass(frozen=True)
class Hypothesis:
    """One root-cause hypothesis: its prior and human-facing framing."""

    key: str
    prior: float
    label: str
    remediation: str


@dataclass(frozen=True)
class Likelihood:
    """The likelihood table for one probe: cost plus P(symbol | hypothesis)."""

    probe_id: str
    cost_seconds: float
    table: dict[str, dict[str, float]]  # table[symbol][hypothesis_key] = probability


@dataclass(frozen=True)
class Spec:
    """The full loaded and validated hypothesis/likelihood spec."""

    hypotheses: dict[str, Hypothesis]
    likelihoods: dict[str, Likelihood]


def load_spec(path: str | Path) -> Spec:
    """Load hypotheses.yaml from `path`, validate it, and return a Spec.

    Raises AssertionError, naming the exact probe/observation/hypothesis at
    fault, if the spec violates any invariant checked by validate_spec().
    """
    raw = yaml.safe_load(Path(path).read_text())
    spec = _build_spec(raw)
    validate_spec(spec)
    return spec


def _build_spec(raw: dict[str, Any]) -> Spec:
    hypotheses = {
        key: Hypothesis(
            key=key,
            prior=fields["prior"],
            label=fields["label"],
            remediation=fields["remediation"],
        )
        for key, fields in raw["hypotheses"].items()
    }
    likelihoods = {
        probe_id: Likelihood(
            probe_id=probe_id,
            cost_seconds=fields["cost_seconds"],
            table=fields["table"],
        )
        for probe_id, fields in raw["likelihoods"].items()
    }
    return Spec(hypotheses=hypotheses, likelihoods=likelihoods)


def validate_spec(spec: Spec) -> None:
    """Assert every hard invariant on a built Spec.

    Every failure names the exact probe, observation symbol, and/or
    hypothesis at fault so a broken hand-filled YAML can be fixed on sight.
    """
    _validate_priors(spec)
    _validate_hypothesis_references(spec)
    _validate_probe_symbol_coverage(spec)
    _validate_likelihood_columns(spec)
    _validate_probability_bounds(spec)


def _validate_priors(spec: Spec) -> None:
    total = sum(h.prior for h in spec.hypotheses.values())
    assert abs(total - 1.0) <= _SUM_TOLERANCE, (
        f"hypothesis priors sum to {total!r}, expected 1.0 "
        f"(within {_SUM_TOLERANCE}); hypotheses: {sorted(spec.hypotheses)}"
    )


def _validate_hypothesis_references(spec: Spec) -> None:
    known_hypotheses = set(spec.hypotheses)
    for probe_id, likelihood in spec.likelihoods.items():
        for symbol, row in likelihood.table.items():
            for hypothesis_key in row:
                assert hypothesis_key in known_hypotheses, (
                    f"likelihoods.{probe_id}.table[{symbol!r}] references unknown "
                    f"hypothesis {hypothesis_key!r}; known hypotheses are "
                    f"{sorted(known_hypotheses)}"
                )


def _validate_probe_symbol_coverage(spec: Spec) -> None:
    for probe_id, allowed_symbols in OBSERVATION_SPACE.items():
        assert probe_id in spec.likelihoods, (
            f"likelihoods spec is missing an entry for probe {probe_id!r}; "
            f"OBSERVATION_SPACE requires one for every probe"
        )
        table_symbols = set(spec.likelihoods[probe_id].table)
        expected_symbols = set(allowed_symbols)
        missing = expected_symbols - table_symbols
        extra = table_symbols - expected_symbols
        assert not missing and not extra, (
            f"likelihoods.{probe_id}.table keys {sorted(table_symbols)} do not "
            f"exactly match OBSERVATION_SPACE[{probe_id!r}] = {sorted(expected_symbols)}; "
            f"missing={sorted(missing)}, extra={sorted(extra)}"
        )


def _validate_likelihood_columns(spec: Spec) -> None:
    for probe_id, likelihood in spec.likelihoods.items():
        for hypothesis_key in spec.hypotheses:
            total = sum(
                row.get(hypothesis_key, 0.0) for row in likelihood.table.values()
            )
            assert abs(total - 1.0) <= _SUM_TOLERANCE, (
                f"likelihoods.{probe_id} column for hypothesis {hypothesis_key!r} "
                f"sums to {total!r} across observations "
                f"{sorted(likelihood.table)}, expected 1.0 (within {_SUM_TOLERANCE})"
            )


def _validate_probability_bounds(spec: Spec) -> None:
    for probe_id, likelihood in spec.likelihoods.items():
        for symbol, row in likelihood.table.items():
            for hypothesis_key, probability in row.items():
                assert _PROBABILITY_MIN <= probability <= _PROBABILITY_MAX, (
                    f"likelihoods.{probe_id}.table[{symbol!r}][{hypothesis_key!r}] = "
                    f"{probability!r} is outside the smoothed range "
                    f"[{_PROBABILITY_MIN}, {_PROBABILITY_MAX}]"
                )
