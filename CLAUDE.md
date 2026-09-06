# BLACK BOX — Diagnosis Engine (Person 3)

Bayesian sequential experimental design for network fault diagnosis.
Consumes SYMBOLS from upstream modules. Produces a probable cause with a
confidence and an auditable reasoning trace.

## Position in the pipeline
Person 1 (raw network collection) → Person 2 (comparison + anomalies)
→ **Person 3 = THIS REPO (diagnosis)** → REST API → React frontend

## Hard invariants — never violate
- The engine NEVER parses raw text or tool output. It reasons only over
  symbols declared in OBSERVATION_SPACE.
- Likelihood columns sum to 1.0 per (probe, hypothesis). Assert on load.
- No probability is ever 0.0 or 1.0. Smoothed range [0.01, 0.99].
- All belief math happens in log space with log-sum-exp normalisation.
- A missing/unmeasurable observation (None) is NOT evidence.
  Record it, do NOT update beliefs on it.
- Probes with unmet preconditions are excluded BEFORE EIG scoring.
- The LLM makes zero diagnostic decisions. It only prose-summarises
  finished JSON.

## Upstream data rules
- Person 1 returns null (not 0) for anything unmeasurable.
  null and 0 mean different things and must never be conflated.
- Person 2's analysis is separate from Person 1's raw data.
  Never mutate raw data.

## Stack
Python 3.11+, numpy, pyyaml, pytest, pytest-asyncio, rich.
No ML frameworks. Nothing is trained.

## Style
Type hints everywhere. Dataclasses for data. No global state.
Every module has tests in tests/test_<module>.py.
Prefer clarity over cleverness — this code gets explained to judges.
