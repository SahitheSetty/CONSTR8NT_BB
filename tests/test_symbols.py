import pytest

from blackbox_engine.symbols import OBSERVATION_SPACE, Observation


def test_valid_measured_observation_validates_silently():
    obs = Observation(
        probe_id="tcp_443",
        symbol="open",
        measured=True,
        duration_ms=12.3,
        raw={"port": 443},
        note=None,
    )
    obs.validate()


def test_unknown_probe_id_raises_and_names_it():
    obs = Observation(
        probe_id="not_a_real_probe",
        symbol=None,
        measured=False,
        duration_ms=None,
        raw={},
        note=None,
    )
    with pytest.raises(ValueError, match="not_a_real_probe"):
        obs.validate()


def test_out_of_vocabulary_symbol_raises_and_names_value_and_allowed_set():
    obs = Observation(
        probe_id="tcp_443",
        symbol="bogus_symbol",
        measured=True,
        duration_ms=5.0,
        raw={},
        note=None,
    )
    with pytest.raises(ValueError) as exc_info:
        obs.validate()

    message = str(exc_info.value)
    assert "bogus_symbol" in message
    for symbol in OBSERVATION_SPACE["tcp_443"]:
        assert symbol in message


def test_unmeasured_observation_with_non_none_symbol_raises():
    obs = Observation(
        probe_id="tcp_443",
        symbol="open",
        measured=False,
        duration_ms=None,
        raw={},
        note="probe was skipped",
    )
    with pytest.raises(ValueError, match="tcp_443"):
        obs.validate()
