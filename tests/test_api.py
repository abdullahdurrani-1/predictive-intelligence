"""API tests. They need the NASA data and trained models, so they are skipped where those are absent (for example in CI)."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_PRESENT = (ROOT / "models" / "fd001_xgboost_point.joblib").exists() and (ROOT / "data" / "raw" / "test_FD001.txt").exists()
pytestmark = pytest.mark.skipif(not ARTIFACTS_PRESENT, reason="trained models or raw data not available")


@pytest.fixture(scope="module")
def client(tmp_path_factory, monkeypatch_module):
    from fastapi.testclient import TestClient

    from api import main

    # Keep test predictions out of the real monitoring log.
    log_file = tmp_path_factory.mktemp("monitoring") / "prediction_log.jsonl"
    monkeypatch_module.setattr(main, "prediction_log_path", lambda: log_file)
    return TestClient(main.app)


@pytest.fixture(scope="module")
def monkeypatch_module():
    patcher = pytest.MonkeyPatch()
    yield patcher
    patcher.undo()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_engine_list_and_model_information(client):
    assert client.get("/engines").json()["engines"] == list(range(1, 101))
    model = client.get("/model").json()
    assert model["rul_cap_cycles"] == 125 and len(model["sensors_used"]) == 14


def test_engine_report_is_internally_consistent(client):
    for engine_id in (1, 37, 54, 100):
        facts = client.get(f"/engines/{engine_id}").json()
        assert 0 <= facts["range_low_cycles"] <= facts["estimate_cycles"] <= 125
        if facts["range_is_open_ended"]:
            assert facts["range_high_cycles"] is None
        else:
            assert facts["estimate_cycles"] <= facts["range_high_cycles"]
        assert len(facts["main_reasons"]) == 4 and "simulated" in facts["data_source"]


def test_unknown_engine_returns_404(client):
    assert client.get("/engines/999").status_code == 404
    assert client.post("/engines/999/ask", json={"question": "Is it healthy?"}).status_code == 404


def test_history_has_estimates_from_cycle_31(client):
    history = client.get("/engines/37/history").json()
    assert history["estimates"]["cycle"][0] == 31 and history["sensors"]["cycle"][-1] == 121


def test_ask_returns_a_grounded_answer(client):
    from src.assistant.assistant import ungrounded_numbers

    facts = client.get("/engines/37").json()
    reply = client.post("/engines/37/ask", json={"question": "How much longer can this engine work?",
                                                 "use_language_model": False}).json()
    assert reply["source"] == "rule-based" and not ungrounded_numbers(reply["answer"], facts)
    assert client.post("/engines/37/ask", json={"question": ""}).status_code == 422


def test_assess_matches_the_stored_engine_and_validates_input(client):
    from api.main import get_service

    service = get_service()
    history = service.history(37)
    readings = [{"cycle": int(row["cycle"]), "sensors": {name: float(row[name]) for name in service.sensors}}
                for _, row in history.iterrows()]
    submitted = client.post("/assess", json={"engine_label": "Engine 37", "readings": readings}).json()
    stored = client.get("/engines/37").json()
    assert submitted["estimate_cycles"] == stored["estimate_cycles"]
    assert submitted["range_low_cycles"] == stored["range_low_cycles"]

    assert client.post("/assess", json={"readings": readings[5:]}).status_code == 422          # does not start at cycle 1
    broken = [{"cycle": 1, "sensors": {"sensor_2": 642.0}}]
    assert client.post("/assess", json={"readings": broken}).status_code == 422               # sensors missing


def test_fleet_datasets_and_sensors(client):
    engines = client.get("/fleet").json()["engines"]
    assert len(engines) == 100 and all(e["range_low_cycles"] <= e["estimate_cycles"] for e in engines)
    assert engines[36]["estimate_cycles"] == client.get("/engines/37").json()["estimate_cycles"]

    datasets = {d["name"]: d for d in client.get("/datasets").json()["datasets"]}
    assert datasets["FD001"]["served"] and not datasets["FD004"]["served"]

    sensors = client.get("/sensors").json()["sensors"]
    assert len(sensors) == 21 and sum(s["used_by_model"] for s in sensors) == 14
    assert next(s for s in sensors if s["name"] == "sensor_11")["station"] == "30"


def test_report_at_an_earlier_cycle_uses_only_earlier_readings(client):
    earlier = client.get("/engines/37", params={"cycle": 60}).json()
    latest = client.get("/engines/37").json()
    assert earlier["cycles_recorded"] == 60 and not earlier["is_latest_cycle"] and latest["is_latest_cycle"]
    assert earlier["estimate_cycles"] > latest["estimate_cycles"]
    history = client.get("/engines/37/history").json()
    at_60 = history["estimates"]["estimate"][history["estimates"]["cycle"].index(60)]
    assert abs(at_60 - earlier["estimate_cycles"]) <= 0.5      # the same number the timeline shows
    assert len(history["sensors"]) == 22 and history["benchmark_label"]["true_rul"] == 21
    assert client.get("/engines/37", params={"cycle": 500}).status_code == 422


def test_research_models_monitoring_settings(client):
    research = client.get("/research").json()
    assert {row["model"] for row in research["ml_test"]} >= {"Random Forest", "XGBoost"}
    assert len(research["all_subsets"]) == 4 and len(research["ml_predictions"]) == 100

    models = client.get("/models").json()
    assert models["served_model"]["architecture"]["trees"] == 400 and models["served_model"]["range"]["target_percent"] == 90

    clean = client.get("/monitoring").json()
    drifted = client.get("/monitoring", params={"inject_drift": True}).json()
    assert not clean["alert"] and drifted["alert"] and drifted["drift"][0]["feature"] == "sensor_11"

    analysis = client.get("/sensors/analysis").json()
    assert len(analysis["correlation"]) == 14 and max(analysis["model_reliance_cycles"], key=analysis["model_reliance_cycles"].get) == "sensor_11"
    assert client.get("/settings").json()["assistant"]["provider"] == "Google Gemini"


def test_assistant_chat_rule_based_is_grounded_and_keeps_engines_apart(client):
    from src.assistant.assistant import numbers_in

    def ask(engine_id, question, **extra):
        body = {"engine_id": engine_id, "messages": [{"role": "user", "content": question}], "use_language_model": False, **extra}
        return client.post("/assistant/chat", json=body).json()

    reply = ask(37, "How much longer can this engine work?")
    assert reply["source"] == "rule-based" and reply["evidence"] and "22" in reply["answer"]
    evidence_numbers = numbers_in(str(reply["evidence"])) | {"1", "9", "10", "90", "100"}
    assert numbers_in(reply["answer"]) <= evidence_numbers | numbers_in(str(client.get("/engines/37").json()))

    assert "120" in ask(54, "How much longer can this engine work?")["answer"]          # a different engine, different facts
    assert "Static pressure" in ask(37, "What does sensor 11 mean?")["answer"]
    compared = ask(37, "Compare this engine with engine 54")
    assert "Engine 37" in compared["answer"] and "Engine 54" in compared["answer"]
    assert "cannot tell you whether" in ask(37, "Is it safe to fly?")["answer"]
    greeting = ask(37, "hi")
    assert greeting["source"].endswith("conversational reply") and greeting["evidence"] == [] and "22" not in greeting["answer"]
    assert "everyday terms" in ask(37, "Is this engine healthy?", plain_language=True)["answer"]
    assert ask(37, "How long?", cycle=60)["evidence"][0]["result"]["flights_recorded"] == 60
    assert client.post("/assistant/chat", json={"engine_id": 999, "messages": [{"role": "user", "content": "hi"}]}).status_code == 404


def test_upload_accepts_good_files_and_refuses_unsuitable_ones(client):
    import pandas as pd
    from io import StringIO

    example = client.get("/uploads/example").text
    good = client.post("/uploads", json={"filename": "engine.csv", "content": example}).json()
    stored = client.get("/engines/37").json()
    assert good["facts"]["estimate_cycles"] == stored["estimate_cycles"] and good["facts"]["data_warnings"] == []
    assert good["history"]["estimates"]["cycle"][0] == 31 and good["file"]["flights"] == 121

    table = pd.read_csv(StringIO(example))

    def upload(frame, **extra):
        return client.post("/uploads", json={"filename": "test.csv", "content": frame.to_csv(index=False), **extra})

    celsius = table.copy()
    celsius[["sensor_2", "sensor_3", "sensor_4"]] = (celsius[["sensor_2", "sensor_3", "sensor_4"]] - 491.67) * 5 / 9
    refused = upload(celsius)
    assert refused.status_code == 422 and "different units" in refused.json()["detail"]["reasons"][0]

    assert upload(table.assign(**{c: table[c] * 3 for c in table.columns if c.startswith("sensor_")})).status_code == 422
    assert upload(table.assign(setting_1=35.0, setting_2=0.84)).status_code == 422          # another flight condition
    assert upload(table.drop(columns=["sensor_11"])).status_code == 422
    assert upload(table.drop(index=range(50, 60))).status_code == 422                       # flights missing

    stuck = table.copy()
    stuck.loc[stuck.index[-40:], "sensor_11"] = stuck["sensor_11"].iloc[:20].mean()
    warned = upload(stuck).json()
    assert len(warned["facts"]["data_warnings"]) == 1 and "sensor 11" in warned["facts"]["data_warnings"][0].lower()

    # The NASA text layout, holding many engines: the user is asked to choose one.
    from pathlib import Path
    nasa = (Path(__file__).resolve().parents[1] / "data" / "raw" / "test_FD001.txt").read_text()
    asked = client.post("/uploads", json={"filename": "test_FD001.txt", "content": nasa}).json()
    assert asked["needs_engine_choice"] and len(asked["engines"]) == 100
    chosen = client.post("/uploads", json={"filename": "test_FD001.txt", "content": nasa, "engine_number": 54}).json()
    assert chosen["facts"]["estimate_cycles"] == client.get("/engines/54").json()["estimate_cycles"]
    assert client.post("/uploads", json={"filename": "x.txt", "content": "hello world"}).status_code == 422


def test_no_demonstration_engine_trips_the_data_checks(client):
    from api.main import get_service

    service = get_service()
    for engine_id in service.engine_ids():
        findings = service.validator.check(service.history(engine_id))
        assert findings.accepted, (engine_id, findings.problems)


def test_downloadable_report(client):
    from io import BytesIO

    from pypdf import PdfReader

    def text_of(response):
        assert response.status_code == 200 and response.headers["content-type"] == "application/pdf"
        assert response.content.startswith(b"%PDF")
        return " ".join(" ".join(page.extract_text() for page in PdfReader(BytesIO(response.content)).pages).split())

    facts = client.get("/engines/37").json()
    response = client.get("/engines/37/report")
    assert response.headers["content-disposition"] == 'attachment; filename="engine_37_report_flight_121.pdf"'
    text = text_of(response)
    assert "Engine report: Engine 37" in text and "21 to 50 flights" in text and "research demonstration on simulated data" in text
    assert f"Estimated flights remaining {facts['estimate_cycles']}" in text
    assert facts["main_reasons"][0]["description"] in text and "not a safety limit" in text

    assert "at least 93 flights" in text_of(client.get("/engines/54/report"))                 # open-ended range
    earlier = client.get("/engines/37/report", params={"cycle": 60})
    assert "flight_60.pdf" in earlier.headers["content-disposition"] and "Flights on record 60" in text_of(earlier)
    assert client.get("/engines/999/report").status_code == 404

    example = client.get("/uploads/example").text
    uploaded = text_of(client.post("/uploads", json={"filename": "my engine.csv", "content": example, "as_report": True}))
    assert "my engine.csv" in uploaded and f"Estimated flights remaining {facts['estimate_cycles']}" in uploaded
