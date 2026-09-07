from pathlib import Path

import pytest

from blackbox_engine.spec_loader import load_spec
from blackbox_engine.symbols import OBSERVATION_SPACE

FIXTURES = Path(__file__).parent / "fixtures"
REAL_SPEC = Path(__file__).parent.parent / "src" / "blackbox_engine" / "hypotheses.yaml"


def test_real_spec_loads_and_validates():
    spec = load_spec(REAL_SPEC)

    assert set(spec.likelihoods) == set(OBSERVATION_SPACE)
    assert abs(sum(h.prior for h in spec.hypotheses.values()) - 1.0) < 1e-6
    for probe_id, likelihood in spec.likelihoods.items():
        assert set(likelihood.table) == set(OBSERVATION_SPACE[probe_id])


def test_bad_column_sum_raises_and_names_probe_and_hypothesis():
    with pytest.raises(AssertionError) as exc_info:
        load_spec(FIXTURES / "spec_bad_column_sum.yaml")

    message = str(exc_info.value)
    assert "dns_resolution" in message
    assert "dns_failure" in message
    assert "0.97" in message


def test_unsmoothed_zero_raises_and_names_probe_symbol_and_hypothesis():
    with pytest.raises(AssertionError) as exc_info:
        load_spec(FIXTURES / "spec_unsmoothed_zero.yaml")

    message = str(exc_info.value)
    assert "dns_resolution" in message
    assert "'ok'" in message
    assert "dns_failure" in message
    assert "0.0" in message


def test_unknown_hypothesis_key_raises_and_names_it():
    with pytest.raises(AssertionError) as exc_info:
        load_spec(FIXTURES / "spec_unknown_hypothesis.yaml")

    message = str(exc_info.value)
    assert "phantom_cause" in message
    assert "dns_resolution" in message
    assert "'ok'" in message


def test_missing_observation_in_table_raises_and_names_it():
    with pytest.raises(AssertionError) as exc_info:
        load_spec(FIXTURES / "spec_missing_observation.yaml")

    message = str(exc_info.value)
    assert "tcp_443" in message
    assert "timeout" in message


def test_priors_not_summing_to_one_raises(tmp_path):
    import yaml

    raw = yaml.safe_load(REAL_SPEC.read_text())
    first_key = next(iter(raw["hypotheses"]))
    raw["hypotheses"][first_key]["prior"] += 0.05

    broken = tmp_path / "spec_bad_priors.yaml"
    broken.write_text(yaml.dump(raw, sort_keys=False))

    with pytest.raises(AssertionError, match="priors sum to"):
        load_spec(broken)


def test_out_of_bounds_prior_raises_even_when_the_sum_is_still_one(tmp_path):
    # A prior outside [0.01, 0.99] can still be masked by the sum-to-1.0
    # check alone if another prior compensates for it -- e.g. {-0.3, 1.3,
    # ...} sums to 1.0 but produces NaN via np.log() instead of failing at
    # load time. Bounds must be checked per hypothesis, not just in total.
    import yaml

    raw = yaml.safe_load(REAL_SPEC.read_text())
    keys = list(raw["hypotheses"])
    raw["hypotheses"][keys[0]]["prior"] -= 0.3
    raw["hypotheses"][keys[1]]["prior"] += 0.3

    broken = tmp_path / "spec_out_of_bounds_prior.yaml"
    broken.write_text(yaml.dump(raw, sort_keys=False))

    with pytest.raises(AssertionError, match=f"hypotheses.{keys[0]}.prior"):
        load_spec(broken)
