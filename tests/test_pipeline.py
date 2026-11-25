"""Tests for the data preparation, metrics and assistant logic.

These use small synthetic data, so they run anywhere (including CI) without
the NASA files or trained models.
"""

import numpy as np
import pandas as pd
import pytest

from src.assistant.answers import answer, detect_intent
from src.assistant.assistant import answer_question, ungrounded_numbers
from src.assistant.knowledge import status_for
from src.data.cmapss import COLUMN_NAMES, add_training_rul
from src.data.splits import engine_folds, holdout_engine_split
from src.evaluation.metrics import mae, nasa_score, rmse
from src.features.build import add_baseline_change, add_rolling_features, cap_rul, make_windows
from src.features.regimes import RegimeScaler
from src.models.uncertainty import calibrated_band, conformal_correction, conformity_scores, enclose_point
from src.monitoring.drift import population_stability_index

SENSORS = ["sensor_2", "sensor_11"]


@pytest.fixture
def fleet() -> pd.DataFrame:
    """Five small engines of different lengths with a drifting sensor."""
    rng = np.random.default_rng(0)
    frames = []
    for engine_id, life in enumerate([40, 55, 35, 60, 45], start=1):
        frame = pd.DataFrame(0.0, index=range(life), columns=COLUMN_NAMES)
        frame["engine_id"], frame["cycle"] = engine_id, np.arange(1, life + 1)
        frame["setting_3"] = 100.0
        frame["sensor_2"] = 640 + rng.normal(0, 0.5, life)
        frame["sensor_11"] = 47 + np.linspace(0, 1, life) ** 2 + rng.normal(0, 0.1, life)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def test_training_rul_counts_down_to_zero(fleet):
    labelled = add_training_rul(fleet)
    assert (labelled.groupby("engine_id")["rul"].min() == 0).all()
    assert labelled.loc[labelled["engine_id"] == 1, "rul"].iloc[0] == 39


def test_cap_limits_labels_only_above_the_cap():
    assert cap_rul(pd.Series([200, 125, 30]), 125).tolist() == [125, 125, 30]
    assert cap_rul(pd.Series([200, 30]), None).tolist() == [200, 30]


def test_features_never_look_into_the_future(fleet):
    full = add_baseline_change(add_rolling_features(fleet, SENSORS, 10), SENSORS, 5)
    cut = fleet[fleet["cycle"] <= 20]
    truncated = add_baseline_change(add_rolling_features(cut, SENSORS, 10), SENSORS, 5)
    engineered = [c for c in full.columns if c.endswith(("_mean10", "_std10", "_delta"))]
    assert np.allclose(full.loc[cut.index, engineered], truncated[engineered])
    assert not full[engineered].isna().any().any()


def test_windows_have_expected_shape_and_labels(fleet):
    labelled = add_training_rul(fleet)
    windows, labels, engines = make_windows(labelled, SENSORS, 10, "rul")
    assert windows.shape == (int((labelled.groupby("engine_id").size() - 9).sum()), 10, 2)
    first = labelled[labelled["engine_id"] == 1]
    assert np.allclose(windows[0], first[SENSORS].to_numpy()[:10])
    assert labels[0] == first["rul"].iloc[9] and labels[engines == 1][-1] == 0


def test_short_history_is_padded_and_last_only_gives_one_window_per_engine(fleet):
    short = fleet[(fleet["engine_id"] == 1) & (fleet["cycle"] <= 4)]
    windows, _, _ = make_windows(short, SENSORS, 10, last_only=True)
    assert windows.shape == (1, 10, 2) and np.allclose(windows[0, :6], windows[0, 0])
    windows, _, engines = make_windows(fleet, SENSORS, 10, last_only=True)
    assert len(windows) == fleet["engine_id"].nunique() == len(engines)


def test_splits_keep_every_engine_on_one_side(fleet):
    training, validation = holdout_engine_split(fleet, validation_fraction=0.4)
    assert not set(training) & set(validation) and len(validation) == 2
    for train_rows, validation_rows in engine_folds(fleet, n_splits=5):
        assert not set(fleet.iloc[train_rows]["engine_id"]) & set(fleet.iloc[validation_rows]["engine_id"])


def test_metrics_on_known_values():
    assert rmse([10, 20], [13, 16]) == pytest.approx(np.sqrt(12.5))
    assert mae([10, 20], [13, 16]) == pytest.approx(3.5)
    assert nasa_score([50], [50]) == 0
    # A late prediction costs more than an equally large early one.
    assert nasa_score([50], [60]) > nasa_score([50], [40]) > 0


def test_regime_scaler_removes_flight_condition_offsets(fleet):
    two_conditions = fleet.copy()
    high_altitude = two_conditions["cycle"] % 2 == 0
    two_conditions.loc[high_altitude, "setting_1"] = 35.0
    two_conditions.loc[high_altitude, "sensor_2"] -= 100.0
    scaled = RegimeScaler().fit(two_conditions, SENSORS).transform(two_conditions)
    assert abs(scaled.loc[high_altitude, "sensor_2"].mean() - scaled.loc[~high_altitude, "sensor_2"].mean()) < 1e-6
    unseen = two_conditions.assign(setting_1=10.0)
    with pytest.raises(ValueError):
        RegimeScaler().fit(two_conditions, SENSORS).transform(unseen)


def test_conformal_correction_and_bands():
    low, high, truth = np.array([10.0, 20.0, 30.0]), np.array([20.0, 30.0, 40.0]), np.array([15.0, 33.0, 28.0])
    scores = conformity_scores(low, high, truth)
    assert scores.tolist() == [-5.0, 3.0, 2.0]
    assert conformal_correction(scores, 0.9) == 3.0
    banded_low, banded_high = calibrated_band(low, high, 3.0, 0, 35)
    assert banded_low.tolist() == [7.0, 17.0, 27.0] and banded_high.tolist() == [23.0, 33.0, 35.0]
    assert enclose_point(np.array([28.0]), np.array([49.0]), np.array([21.6]))[0][0] == 21.6


def test_population_stability_index():
    rng = np.random.default_rng(1)
    reference = rng.normal(0, 1, 5000)
    assert population_stability_index(reference, rng.normal(0, 1, 5000)) < 0.05
    assert population_stability_index(reference, rng.normal(1.5, 1, 5000)) > 0.25


FACTS = {
    "engine": "Engine 7", "cycles_recorded": 121, "limited_history": False, "estimate_cycles": 22,
    "range_low_cycles": 21, "range_high_cycles": 50, "range_is_open_ended": False, "rul_cap_cycles": 125,
    "status": status_for(22, 21, False), "model_average_estimate_cycles": 87,
    "main_reasons": [{"sensor": "sensor_11", "symbol": "Ps30", "description": "Static pressure at HPC outlet",
                      "cycles": -16.6, "unit": "psia", "early_life_level": 47.18, "recent_level": 47.56,
                      "change_percent": 0.81, "movement": "higher than", "effect": "lowers the estimate"}],
    "model": {"typical_error_cycles": 11, "measured_range_coverage_percent": 95.0},
}


def test_status_bands():
    assert status_for(22, 21, False)["key"] == "near_end_of_predicted_life"
    assert status_for(45, 30, False)["key"] == "advanced_wear"
    assert status_for(80, 50, True)["key"] == "early_wear"
    assert status_for(120, 93, True)["key"] == "no_measurable_wear"


@pytest.mark.parametrize("question, intent", [
    ("Is this engine healthy?", "health"), ("How much longer can this engine work?", "life"),
    ("Why is the engine becoming unhealthy?", "why"), ("What should we do now?", "action"),
    ("Is it safe to fly?", "safe"), ("How reliable is this prediction?", "reliability"),
])
def test_intent_detection(question, intent):
    assert detect_intent(question) == intent


@pytest.mark.parametrize("question", ["Is this engine healthy?", "How long will it last?", "Why?", "What should we do?",
                                      "Can it fly?", "Can I trust this?", "What happens if we keep flying?", "Tell me more"])
def test_rule_based_answers_state_only_numbers_from_the_fact_sheet(question):
    reply = answer(question, FACTS)
    assert not ungrounded_numbers(reply, FACTS)
    assert "approved maintenance procedures" in reply


def test_assistant_never_clears_an_engine_to_fly():
    reply = answer("Is it safe to fly?", FACTS).lower()
    assert "cannot tell you whether" in reply and "clearance" in reply


def test_open_ended_range_is_reported_as_at_least():
    facts = {**FACTS, "estimate_cycles": 120, "range_low_cycles": 93, "range_high_cycles": None,
             "range_is_open_ended": True, "status": status_for(120, 93, True)}
    reply = answer("How long will it last?", facts)
    assert "at least 93" in reply and "None" not in reply


def test_grounding_check_catches_invented_numbers():
    assert ungrounded_numbers("About 22 flights remain, range 21 to 50.", FACTS) == set()
    assert ungrounded_numbers("About 35 flights remain.", FACTS) == {"35"}


def test_assistant_falls_back_without_credentials(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    reply = answer_question("Is this engine healthy?", FACTS)
    assert reply["source"] == "rule-based" and "no API credential" in reply["note"]


@pytest.mark.parametrize("message, expected", [
    ("hi", True), ("Hello!", True), ("hey there", True), ("thanks", True), ("Thank you very much", True),
    ("who are you?", True), ("what can you do", True), ("good morning", True), ("ok", True), ("bye", True),
    ("hi, is this engine healthy?", False), ("how long will it last", False), ("is it safe to fly", False),
    ("what does sensor 11 mean", False), ("good, now compare with engine 54", False),
])
def test_small_talk_is_recognised(message, expected):
    from src.assistant.chat import is_small_talk
    assert is_small_talk(message) is expected


@pytest.mark.parametrize("message, expected", [
    ("hi, is this engine healthy?", "is this engine healthy?"), ("Hello there! how long will it last", "how long will it last"),
    ("hey why is it wearing", "why is it wearing"), ("hi", "hi"), ("hi there", "hi there"), ("hi, thanks", "hi, thanks"),
    ("highly worn?", "highly worn?"), ("how long will it last", "how long will it last"),
])
def test_greeting_in_front_of_a_question_is_dropped(message, expected):
    from src.assistant.chat import without_greeting
    assert without_greeting(message) == expected


def test_small_talk_replies_state_nothing_about_the_engine():
    from src.assistant.assistant import numbers_in
    from src.assistant.chat import small_talk_reply
    for message in ["hi", "thanks", "who are you?", "how are you", "ok", "bye"]:
        reply = small_talk_reply(message, 37)
        assert numbers_in(reply) <= {"37"} and "flights remaining" not in reply
