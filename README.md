# BLACK BOX — Diagnosis Engine

Bayesian sequential experimental design for network fault diagnosis.

Given a fixed vocabulary of network-probe outcomes, the engine maintains a
posterior distribution over a fixed set of root-cause hypotheses, picks the
next probe to run by expected-information-gain-per-second, updates its
belief in log space as results come in, and stops when it is confident, out
of budget, or out of useful probes to run. Every step of that process is
emitted as an auditable event — nothing is decided off the record.

## Position in the pipeline

```
Person 1 (raw network collection) → Person 2 (comparison + anomalies)
    → Person 3 = THIS REPO (diagnosis) → REST API → React frontend
```

This repo owns diagnosis only. It never touches raw collection or the
frontend, and it never parses free text — it reasons exclusively over the
symbols declared in `OBSERVATION_SPACE` (`symbols.py`).

## Hard invariants

These are enforced in code and tests, not just convention:

- The engine never parses raw text or tool output — it reasons only over
  symbols declared in `OBSERVATION_SPACE`.
- Likelihood columns sum to 1.0 per (probe, hypothesis). Asserted on load.
- No probability is ever `0.0` or `1.0` — smoothed to the range `[0.01, 0.99]`.
- All belief math happens in log space with log-sum-exp normalisation.
- A missing/unmeasurable observation (`None`) is **not** evidence: it is
  recorded, but never used to update beliefs or charge the time budget.
- Probes with unmet preconditions are excluded *before* EIG scoring.
- Person 1 returns `null` (not `0`) for anything unmeasurable — `null` and
  `0` mean different things and must never be conflated.
- Person 2's analysis is derived data; the adapter never mutates Person 1's
  raw data.
- The LLM (when wired up downstream) makes zero diagnostic decisions — it
  only prose-summarises finished JSON.

## Architecture

Person 1 collection (`app/`) gathers DNS, HTTP, TCP-connect, TLS-handshake,
and traceroute evidence for a target:

```text
Target
   |
   +----------+----------+----------+
   |          |          |          |
   v          v          v          v
  DNS        TCP        TLS        HTTP
   |          |          |          |
   +----------+----+-----+----------+
                   |
                   v
              Traceroute
                   |
                   v
           Structured Evidence
                   |
                   v
               Person 2
```

`app/pipeline.py` is where that raw evidence, Person 2's path comparison,
and the diagnosis engine below actually meet: it adapts both into
`blackbox_engine`'s contracts, drives one `Investigation`, and shapes the
verdict into the JSON the frontend renders.

```
src/blackbox_engine/
  symbols.py       Fixed OBSERVATION_SPACE vocabulary, probe PRECONDITIONS,
                    and the Observation dataclass (probe_id, symbol,
                    measured, duration_ms, raw, note) with validate().

  adapter.py        Translates Person 1 (raw) + Person 2 (analysis) JSON into
                    Observations. The engine's only point of contact with the
                    outside world; any upstream contract gap fails safe
                    (measured=False, symbol=None, note explaining the gap)
                    rather than guessing a symbol.

  spec_loader.py    Loads and validates hypotheses.yaml into a Spec
                    (Hypothesis priors + per-probe Likelihood tables).
                    Every invariant (priors sum to 1, likelihood columns sum
                    to 1, probability bounds, symbol coverage, hypothesis
                    references) is asserted at load time, naming the exact
                    probe/observation/hypothesis at fault.

  hypotheses.yaml   Hand-filled spec: 12 root-cause hypotheses (priors,
                    labels, remediation text) and, for every probe in
                    OBSERVATION_SPACE, a likelihood table + probe cost in
                    seconds. Likelihoods are tuned against StochasticMock
                    (see evaluation.py): 86.9% overall accuracy.

  belief_state.py   BeliefState: a normalised log-probability distribution
                    over the hypothesis list. update() combines a
                    per-hypothesis log-likelihood additively in log space and
                    renormalises via log-sum-exp. Also exposes entropy() and
                    top(k).

  test_selector.py  TestSelector: eligible() filters candidate probes by
                    PRECONDITIONS; eig() computes expected information gain
                    in bits for a probe given the current belief; rank()
                    scores eligible probes by gain / cost_seconds, sorted
                    descending, with deterministic tie-breaking.

  orchestrator.py   Investigation: the select → consume → update → stop
                    async loop that drives one target through the engine.
                    Yields ProbeSelected, ProbeUnmeasured, BeliefUpdated, and
                    a terminal Verdict event. Stops on confidence threshold,
                    time budget, no eligible probes, or no informative probes
                    left.

  mocks.py          Probe runners used ahead of Person 1/2's real collectors:
                    ScenarioMock (scripted probe→symbol fixtures, one per
                    hypothesis in SCENARIOS), StochasticMock (samples from
                    the spec's own likelihood table for a known-true
                    hypothesis), FlakyMock (wraps another runner and injects
                    measured=False failures), and ReplayMock (serves
                    pre-adapted Observations from a real Person 1 + Person 2
                    run — the production code path).

  cli.py            Rich-rendered terminal UI (`blackbox` entry point) that
                    drives an Investigation live: belief-distribution bars,
                    a step-by-step probe history, and a verdict panel. Purely
                    a renderer of orchestrator events — it makes no
                    diagnostic decisions itself.
```

## Requirements

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) (or `pip`) for dependency management

Runtime dependencies: `numpy`, `pyyaml`, `rich`, `pandas`, `matplotlib`.
No ML frameworks — nothing in this repo is trained.

## Setup

```bash
uv sync
```

This creates `.venv` and installs the project (editable) plus the `dev`
dependency group (`pytest`, `pytest-asyncio`, `ruff`).

## Running the CLI

The `blackbox` entry point runs one investigation with a live terminal
dashboard. It needs either a scripted scenario or a replayed Person 1 + 2
JSON file as its probe source:

```bash
# Replay one of the built-in scripted hypothesis scenarios
uv run blackbox example.com --scenario tls_failure

# Slow the animation down for a demo
uv run blackbox example.com --scenario congestion_loss --slow

# Run against saved real (or fixture) Person 1 + Person 2 output
uv run blackbox example.com --replay tests/fixtures/combined_sample.json
```

The target is optional -- neither source is a live lookup, so it's only
used to label the run. Omit it and `--scenario` defaults to `demo-<name>`;
`--replay` defaults to the replay file's own `p1_raw.target`.

`--replay` expects a JSON file shaped `{"p1_raw": {...}, "p2_analysis": {...}}`
(see `tests/fixtures/p1_sample.json` / `p2_sample.json` for the shape each
half takes); it's run through `adapter.to_observations` before the
investigation starts.

Other flags: `--spec PATH` (default: the bundled `hypotheses.yaml`),
`--budget SECONDS` (default `30.0`), `--threshold PROBABILITY` (default
`0.85`). Available scenarios: `dns_failure`, `auth_ns_down`,
`routing_blackhole`, `path_change_degraded`, `congestion_loss`,
`server_down`, `app_layer_error`, `tls_failure`, `waf_or_rate_limited`,
`local_vantage_bad`, `mtu_blackhole`, `client_local_issue`.

## Testing

```bash
uv run pytest
```

Every module has a matching `tests/test_<module>.py`. `pytest-asyncio` runs
in `auto` mode (see `pyproject.toml`) so `async def` tests need no marker.
Spec-validation failure fixtures live under `tests/fixtures/` (e.g.
`spec_bad_column_sum.yaml`, `spec_unsmoothed_zero.yaml`).

## Linting

```bash
uv run ruff check .
```

## API

- `POST /investigate` -- Person 1 raw collection only (DNS, HTTP, TCP, TLS, traceroute), returned as-is.
- `POST /diagnose` -- the full pipeline: collect, compare against the previous run of the same target (Person 2), then run the Bayesian diagnosis engine (Person 3) and return one combined result shaped for the frontend. This is what the React app calls.

Both take `{"target": "<domain or IP>"}`.

## Status / known placeholders

- `adapter.py`'s latency-bucket thresholds (`_LATENCY_DELTA_THRESHOLDS_MS`,
  `_LATENCY_ABSOLUTE_THRESHOLDS_MS`) are placeholders pending tuning.
- `dns_consistency`, `external_vantage`, and `mtu_behaviour` have no live
  collector yet -- `adapter.py` reports them unmeasured rather than guessing.
- Several other Person 1 upstream contract gaps are already handled
  defensively (e.g. a bare `http.reachable` boolean can't disambiguate
  refused / timeout / reset for `tcp_443`, so the adapter reports it
  unmeasured rather than guessing).

## Style

Type hints everywhere, dataclasses for data, no global state. Every module
is paired with tests in `tests/test_<module>.py`. Code favors clarity over
cleverness — it needs to be explainable to judges.
