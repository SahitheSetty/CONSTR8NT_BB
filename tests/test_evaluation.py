import numpy as np
import pandas as pd
import pytest

from blackbox_engine.evaluation import (
    accuracy_by_hypothesis,
    calibration_curve,
    confusion_matrix,
    evaluate,
    observation_efficiency,
    overall_accuracy,
    plot_calibration_curve,
    plot_confusion_matrix,
    run_evaluation,
)
from blackbox_engine.mocks import SCENARIOS
from blackbox_engine.spec_loader import Hypothesis, Likelihood, Spec
from blackbox_engine.symbols import OBSERVATION_SPACE

# Reuses SCENARIOS' hand-written fingerprints as a strong (but still
# smoothed) signal, same rationale as test_orchestrator.py: the shipped
# hypotheses.yaml carries placeholder uniform likelihoods with zero
# information gain, so it can't exercise diagnostic accuracy at all.
_SIGNAL_STRENGTH = 0.9
_HYPOTHESES = list(SCENARIOS)


def _calibrated_table(probe: str, hypotheses: list[str]) -> dict[str, dict[str, float]]:
    symbols = OBSERVATION_SPACE[probe]
    table = {symbol: {} for symbol in symbols}
    for hypothesis in hypotheses:
        target_symbol = SCENARIOS[hypothesis][probe]
        spread = (1.0 - _SIGNAL_STRENGTH) / (len(symbols) - 1)
        for symbol in symbols:
            table[symbol][hypothesis] = _SIGNAL_STRENGTH if symbol == target_symbol else spread
    return table


def _build_calibrated_spec() -> Spec:
    hyp_objects = {
        h: Hypothesis(key=h, prior=1.0 / len(_HYPOTHESES), label=h, remediation="n/a")
        for h in _HYPOTHESES
    }
    likelihoods = {
        probe: Likelihood(probe_id=probe, cost_seconds=1.0, table=_calibrated_table(probe, _HYPOTHESES))
        for probe in OBSERVATION_SPACE
    }
    return Spec(hypotheses=hyp_objects, likelihoods=likelihoods)


@pytest.fixture(scope="module")
def calibrated_spec() -> Spec:
    return _build_calibrated_spec()


@pytest.fixture(scope="module")
async def evaluation_results(calibrated_spec) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    return await run_evaluation(calibrated_spec, n_per_hypothesis=5, rng=rng, budget_s=60.0)


async def test_run_evaluation_has_one_row_per_investigation(calibrated_spec):
    rng = np.random.default_rng(1)
    results = await run_evaluation(calibrated_spec, n_per_hypothesis=3, rng=rng, budget_s=60.0)

    assert len(results) == 3 * len(_HYPOTHESES)
    assert list(results.columns) == [
        "truth", "predicted", "correct", "confidence", "n_observations", "stop_reason",
    ]
    assert set(results["truth"]) == set(_HYPOTHESES)
    assert results["correct"].tolist() == (results["truth"] == results["predicted"]).tolist()
    assert results["confidence"].between(0.0, 1.0).all()
    assert (results["n_observations"] > 0).all()


async def test_run_evaluation_is_reproducible_for_a_fixed_seed(calibrated_spec):
    results_a = await run_evaluation(
        calibrated_spec, n_per_hypothesis=3, rng=np.random.default_rng(42), budget_s=60.0
    )
    results_b = await run_evaluation(
        calibrated_spec, n_per_hypothesis=3, rng=np.random.default_rng(42), budget_s=60.0
    )

    pd.testing.assert_frame_equal(results_a, results_b)


async def test_strong_signal_spec_beats_random_guessing(evaluation_results):
    # With a strong (0.9) per-probe signal this should diagnose correctly
    # far more often than the 1/12 chance rate; not asserting near-100%
    # since StochasticMock samples noisily and can mislead the engine.
    assert overall_accuracy(evaluation_results) > 0.5


async def test_accuracy_by_hypothesis_covers_every_hypothesis_in_unit_interval(evaluation_results):
    per_hypothesis = accuracy_by_hypothesis(evaluation_results)

    assert list(per_hypothesis.index) == sorted(_HYPOTHESES)
    assert per_hypothesis.between(0.0, 1.0).all()


async def test_confusion_matrix_is_square_and_sums_to_row_count(calibrated_spec, evaluation_results):
    matrix = confusion_matrix(evaluation_results, hypotheses=list(calibrated_spec.hypotheses))

    assert list(matrix.index) == list(calibrated_spec.hypotheses)
    assert list(matrix.columns) == list(calibrated_spec.hypotheses)
    assert int(matrix.values.sum()) == len(evaluation_results)
    # diagonal (correct calls) should dominate given the strong signal
    diagonal = sum(matrix.loc[h, h] for h in calibrated_spec.hypotheses)
    assert diagonal == evaluation_results["correct"].sum()


async def test_confusion_matrix_defaults_to_observed_labels(calibrated_spec):
    rng = np.random.default_rng(7)
    results = await run_evaluation(calibrated_spec, n_per_hypothesis=1, rng=rng, budget_s=60.0)

    matrix = confusion_matrix(results)

    observed = sorted(set(results["truth"]) | set(results["predicted"]))
    assert list(matrix.index) == observed
    assert list(matrix.columns) == observed


async def test_observation_efficiency_stays_within_available_probes(calibrated_spec, evaluation_results):
    efficiency = observation_efficiency(evaluation_results, calibrated_spec)

    assert efficiency["total_available_probes"] == len(calibrated_spec.likelihoods)
    assert 0.0 < efficiency["mean_observations"] <= efficiency["total_available_probes"]
    assert efficiency["mean_fraction_used"] == pytest.approx(
        efficiency["mean_observations"] / efficiency["total_available_probes"]
    )


async def test_calibration_curve_bins_cover_the_unit_interval_and_all_rows(evaluation_results):
    curve = calibration_curve(evaluation_results, n_bins=10)

    assert list(curve.columns) == [
        "bin_low", "bin_high", "bin_mid", "mean_confidence", "observed_accuracy", "count",
    ]
    assert (curve["bin_low"] >= 0.0).all()
    assert (curve["bin_high"] <= 1.0).all()
    assert (curve["bin_low"] < curve["bin_high"]).all()
    assert curve["bin_low"].is_monotonic_increasing
    assert curve["observed_accuracy"].between(0.0, 1.0).all()
    assert int(curve["count"].sum()) == len(evaluation_results)


async def test_calibration_curve_on_empty_results_has_no_rows():
    empty = pd.DataFrame(
        columns=["truth", "predicted", "correct", "confidence", "n_observations", "stop_reason"]
    )
    curve = calibration_curve(empty, n_bins=10)
    assert curve.empty


async def test_plot_confusion_matrix_writes_a_nonempty_file(
    calibrated_spec, evaluation_results, tmp_path
):
    matrix = confusion_matrix(evaluation_results, hypotheses=list(calibrated_spec.hypotheses))
    out_path = tmp_path / "nested" / "confusion.png"

    result_path = plot_confusion_matrix(matrix, out_path)

    assert result_path == out_path
    assert out_path.exists()
    assert out_path.stat().st_size > 0


async def test_plot_calibration_curve_writes_a_nonempty_file(evaluation_results, tmp_path):
    curve = calibration_curve(evaluation_results)
    out_path = tmp_path / "nested" / "calibration.png"

    result_path = plot_calibration_curve(curve, out_path)

    assert result_path == out_path
    assert out_path.exists()
    assert out_path.stat().st_size > 0


async def test_evaluate_bundles_every_metric_consistently(calibrated_spec):
    report = await evaluate(calibrated_spec, n_per_hypothesis=2, seed=3, budget_s=60.0)

    assert len(report.results) == 2 * len(_HYPOTHESES)
    assert report.overall_accuracy == overall_accuracy(report.results)
    assert list(report.confusion.index) == list(calibrated_spec.hypotheses)
    assert report.observation_efficiency["total_available_probes"] == len(calibrated_spec.likelihoods)
