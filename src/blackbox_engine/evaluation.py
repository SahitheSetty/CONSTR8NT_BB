"""Offline accuracy evaluation of the diagnosis engine against StochasticMock.

Runs many simulated investigations per hypothesis, where each observation
is sampled from the spec's own likelihood table for a known ground truth,
then measures how often the engine's verdict matches that truth. This is
the check against the handbook's target of 85-92% accuracy -- near 100%
means the likelihood table is unrealistically clean, not that the engine
is unusually good.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from blackbox_engine.mocks import StochasticMock
from blackbox_engine.orchestrator import Investigation, Verdict
from blackbox_engine.spec_loader import Spec, load_spec

_DEFAULT_SPEC_PATH = Path(__file__).parent / "hypotheses.yaml"
_DEFAULT_REPORTS_DIR = Path(__file__).parent.parent.parent / "reports"
_EVAL_TARGET = "eval.internal"

_RESULT_COLUMNS = ["truth", "predicted", "correct", "confidence", "n_observations", "stop_reason"]


async def _run_one(
    spec: Spec, truth: str, rng: np.random.Generator, budget_s: float, threshold: float
) -> dict:
    mock = StochasticMock(spec, truth, rng)
    investigation = Investigation(_EVAL_TARGET, spec, mock, budget_s=budget_s, threshold=threshold)

    verdict: Verdict | None = None
    async for event in investigation.run():
        if isinstance(event, Verdict):
            verdict = event
    assert verdict is not None

    n_observations = sum(1 for entry in verdict.evidence if entry.measured)
    return {
        "truth": truth,
        "predicted": verdict.top_hypothesis,
        "correct": verdict.top_hypothesis == truth,
        "confidence": verdict.confidence,
        "n_observations": n_observations,
        "stop_reason": verdict.stop_reason,
    }


async def run_evaluation(
    spec: Spec,
    n_per_hypothesis: int,
    rng: np.random.Generator,
    budget_s: float = 30.0,
    threshold: float = 0.85,
) -> pd.DataFrame:
    """Run `n_per_hypothesis` StochasticMock investigations for every hypothesis in `spec`.

    Each row is one investigation: the true hypothesis it was sampled
    under, the engine's verdict, and how it got there. Rows are produced
    in (hypothesis, replicate) order against the single shared `rng`, so
    results are reproducible for a fixed seed but not independent of
    ordering if you rerun with a different `n_per_hypothesis`.
    """
    rows = [
        await _run_one(spec, truth, rng, budget_s, threshold)
        for truth in spec.hypotheses
        for _ in range(n_per_hypothesis)
    ]
    return pd.DataFrame(rows, columns=_RESULT_COLUMNS)


def overall_accuracy(results: pd.DataFrame) -> float:
    """Fraction of investigations whose top hypothesis matched the truth."""
    return float(results["correct"].mean())


def accuracy_by_hypothesis(results: pd.DataFrame) -> pd.Series:
    """Accuracy, grouped by true hypothesis, sorted by hypothesis name."""
    return results.groupby("truth")["correct"].mean().sort_index()


def confusion_matrix(results: pd.DataFrame, hypotheses: list[str] | None = None) -> pd.DataFrame:
    """Counts of (truth, predicted) pairs as a square, zero-filled DataFrame.

    `hypotheses` fixes the row/column order and includes hypotheses that
    never appear as a prediction; defaults to the sorted union of truths
    and predictions actually seen.
    """
    labels = (
        hypotheses
        if hypotheses is not None
        else sorted(set(results["truth"]) | set(results["predicted"]))
    )
    matrix = pd.crosstab(results["truth"], results["predicted"])
    return matrix.reindex(index=labels, columns=labels, fill_value=0)


def observation_efficiency(results: pd.DataFrame, spec: Spec) -> dict[str, float]:
    """Mean probes consumed per verdict, against the total probes the spec defines."""
    total_available = len(spec.likelihoods)
    mean_observations = float(results["n_observations"].mean())
    return {
        "mean_observations": mean_observations,
        "total_available_probes": float(total_available),
        "mean_fraction_used": mean_observations / total_available,
    }


def calibration_curve(results: pd.DataFrame, n_bins: int = 10) -> pd.DataFrame:
    """Bin verdict confidence into `n_bins` equal-width buckets in [0, 1].

    For each non-empty bucket: the mean predicted confidence, the observed
    accuracy among rows in that bucket, and how many rows fell there. A
    well-calibrated engine has observed_accuracy ~= mean_confidence in
    every bucket -- i.e. the points sit near the y=x diagonal.
    """
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    buckets = pd.cut(results["confidence"], bins=edges, include_lowest=True)

    rows = []
    for interval, group in results.groupby(buckets, observed=True):
        if group.empty:
            continue
        rows.append(
            {
                "bin_low": float(interval.left),
                "bin_high": float(interval.right),
                "bin_mid": float((interval.left + interval.right) / 2),
                "mean_confidence": float(group["confidence"].mean()),
                "observed_accuracy": float(group["correct"].mean()),
                "count": len(group),
            }
        )
    rows.sort(key=lambda row: row["bin_low"])
    return pd.DataFrame(
        rows, columns=["bin_low", "bin_high", "bin_mid", "mean_confidence", "observed_accuracy", "count"]
    )


def plot_confusion_matrix(matrix: pd.DataFrame, path: str | Path) -> Path:
    """Render a confusion-matrix heatmap with cell counts to `path`."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    side = max(6.0, 0.6 * len(matrix))
    fig, ax = plt.subplots(figsize=(side, side))
    im = ax.imshow(matrix.values, cmap="Blues")
    ax.set_xticks(range(len(matrix.columns)))
    ax.set_xticklabels(matrix.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(matrix.index)))
    ax.set_yticklabels(matrix.index)
    ax.set_xlabel("predicted")
    ax.set_ylabel("truth")
    ax.set_title("confusion matrix")

    peak = matrix.values.max() if matrix.values.size else 0
    for i in range(len(matrix.index)):
        for j in range(len(matrix.columns)):
            value = matrix.values[i, j]
            ax.text(
                j, i, str(value), ha="center", va="center",
                color="white" if peak and value > peak / 2 else "black",
            )

    fig.colorbar(im, ax=ax, label="count")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_calibration_curve(calibration: pd.DataFrame, path: str | Path) -> Path:
    """Plot observed accuracy vs. mean predicted confidence per bucket, with the y=x diagonal."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot([0, 1], [0, 1], linestyle="--", color="grey", label="perfectly calibrated")
    ax.plot(
        calibration["mean_confidence"], calibration["observed_accuracy"],
        marker="o", color="tab:blue", label="observed",
    )
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("predicted confidence")
    ax.set_ylabel("observed accuracy")
    ax.set_title("calibration curve")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


@dataclass(frozen=True)
class EvaluationReport:
    """Everything `evaluate()` computes from one batch of simulated investigations."""

    results: pd.DataFrame
    overall_accuracy: float
    accuracy_by_hypothesis: pd.Series
    confusion: pd.DataFrame
    observation_efficiency: dict[str, float]
    calibration: pd.DataFrame


async def evaluate(
    spec: Spec,
    n_per_hypothesis: int = 30,
    seed: int = 0,
    budget_s: float = 30.0,
    threshold: float = 0.85,
) -> EvaluationReport:
    """Run the full evaluation suite against `spec` and compute every metric."""
    rng = np.random.default_rng(seed)
    results = await run_evaluation(spec, n_per_hypothesis, rng, budget_s, threshold)
    return EvaluationReport(
        results=results,
        overall_accuracy=overall_accuracy(results),
        accuracy_by_hypothesis=accuracy_by_hypothesis(results),
        confusion=confusion_matrix(results, hypotheses=list(spec.hypotheses)),
        observation_efficiency=observation_efficiency(results, spec),
        calibration=calibration_curve(results),
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="blackbox-eval",
        description="Evaluate diagnosis accuracy by simulating investigations against StochasticMock.",
    )
    parser.add_argument("--spec", default=str(_DEFAULT_SPEC_PATH), help="path to hypotheses.yaml")
    parser.add_argument("--n-per-hypothesis", type=int, default=30, help="investigations per hypothesis")
    parser.add_argument("--seed", type=int, default=0, help="StochasticMock RNG seed")
    parser.add_argument("--budget", type=float, default=30.0, help="time budget in seconds")
    parser.add_argument("--threshold", type=float, default=0.85, help="confidence threshold to stop at")
    parser.add_argument(
        "--reports-dir", default=str(_DEFAULT_REPORTS_DIR), help="directory to write CSV + plots into"
    )
    return parser.parse_args(argv)


async def _main_async(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    spec = load_spec(args.spec)
    report = await evaluate(spec, args.n_per_hypothesis, args.seed, args.budget, args.threshold)

    reports_dir = Path(args.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    results_path = reports_dir / "evaluation_results.csv"
    confusion_path = reports_dir / "confusion_matrix.png"
    calibration_path = reports_dir / "calibration_curve.png"

    report.results.to_csv(results_path, index=False)
    plot_confusion_matrix(report.confusion, confusion_path)
    plot_calibration_curve(report.calibration, calibration_path)

    eff = report.observation_efficiency
    print(f"overall accuracy: {report.overall_accuracy:.1%}  (n={len(report.results)})")
    print(
        f"mean observations to verdict: {eff['mean_observations']:.1f} / "
        f"{eff['total_available_probes']:.0f} available probes "
        f"({eff['mean_fraction_used']:.1%})"
    )
    print("\naccuracy by hypothesis:")
    for hypothesis, accuracy in report.accuracy_by_hypothesis.items():
        print(f"  {hypothesis:<24} {accuracy:.1%}")
    print(f"\nsaved: {results_path}, {confusion_path}, {calibration_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_main_async(argv))


if __name__ == "__main__":
    sys.exit(main())
