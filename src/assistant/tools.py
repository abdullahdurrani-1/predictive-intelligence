"""The tool layer between the language model and the prediction system.

The language model cannot read engine data. It can only call the functions in
`EngineTools`, each of which returns real output from the engine service. Every
call is recorded, so an answer can show the evidence it was built from and be
checked against it.
"""

import json

from src.assistant.knowledge import GLOSSARY, LIMITATIONS
from src.data.cmapss import SENSOR_INFO, SENSOR_STATION, STATION_NAMES
from src.service.engine_service import EngineService

# Plain-language notes on what each kind of measurement is, for "what does sensor N mean?".
SENSOR_PLAIN = {
    "T": "a temperature inside the engine",
    "P": "a pressure inside the engine",
    "N": "how fast one of the engine's shafts is spinning",
    "epr": "the ratio of pressure leaving the engine to pressure entering it",
    "phi": "how much fuel is being burned relative to the pressure in the compressor",
    "BPR": "how much air goes around the engine core compared with through it",
    "farB": "the mix of fuel and air being burned",
    "htBleed": "the energy of air taken (bled) from the compressor",
    "W": "the flow of cooling air taken from the compressor for the turbine",
}


def plain_meaning(symbol: str) -> str:
    for prefix in ("epr", "phi", "BPR", "farB", "htBleed"):
        if symbol.startswith(prefix):
            return SENSOR_PLAIN[prefix]
    return SENSOR_PLAIN.get(symbol[0], "a measurement taken on the engine")


class EngineTools:
    """Tools for one conversation turn. `selected_engine` is the engine open on screen."""

    def __init__(self, service: EngineService, selected_engine: int, cycle: int | None = None):
        self.service = service
        self.selected_engine = selected_engine
        self.cycle = cycle
        self.evidence: list[dict] = []

    # ---- bookkeeping ---------------------------------------------------------------

    def _record(self, tool: str, arguments: dict, result: dict) -> dict:
        self.evidence.append({"tool": tool, "arguments": arguments, "result": result})
        return result

    def _facts(self, engine_id: int) -> dict:
        # The flight selected on screen applies to the selected engine only.
        cycle = self.cycle if engine_id == self.selected_engine else None
        return self.service.report(engine_id, cycle)

    def evidence_text(self) -> str:
        return json.dumps([item["result"] for item in self.evidence])

    # ---- tools the language model may call --------------------------------------

    def get_engine_summary(self, engine_id: int) -> dict:
        """Status, estimated flights remaining, range and recorded history length for one engine.

        Args:
            engine_id: Engine number, 1 to 100.
        """
        try:
            facts = self._facts(engine_id)
        except (KeyError, ValueError) as error:
            return self._record("get_engine_summary", {"engine_id": engine_id}, {"error": str(error)})
        return self._record("get_engine_summary", {"engine_id": engine_id}, {
            "engine": facts["engine"], "data_source": facts["data_source"],
            "flights_recorded": facts["cycles_recorded"], "limited_history": facts["limited_history"],
            "data_warnings": facts.get("data_warnings", []),
            "status": facts["status"]["label"], "status_explanation": facts["status"]["plain"],
            "status_basis": facts["status"]["basis"], "something_to_consider": facts["status"]["consider"],
            "estimated_flights_remaining": facts["estimate_cycles"],
            "range_low": facts["range_low_cycles"], "range_high": facts["range_high_cycles"],
            "range_is_open_ended": facts["range_is_open_ended"],
        })

    def predict_remaining_useful_life(self, engine_id: int) -> dict:
        """The model's estimate of flights remaining for one engine.

        Args:
            engine_id: Engine number, 1 to 100.
        """
        try:
            facts = self._facts(engine_id)
        except (KeyError, ValueError) as error:
            return self._record("predict_remaining_useful_life", {"engine_id": engine_id}, {"error": str(error)})
        return self._record("predict_remaining_useful_life", {"engine_id": engine_id}, {
            "engine": facts["engine"], "estimated_flights_remaining": facts["estimate_cycles"],
            "as_of_flight": facts["cycles_recorded"], "model_limit_flights": facts["rul_cap_cycles"],
            "note": "An estimate from a statistical model, not a guaranteed lifespan.",
        })

    def get_prediction_uncertainty(self, engine_id: int) -> dict:
        """The range around the estimate and how reliable that range has been measured to be.

        Args:
            engine_id: Engine number, 1 to 100.
        """
        try:
            facts = self._facts(engine_id)
        except (KeyError, ValueError) as error:
            return self._record("get_prediction_uncertainty", {"engine_id": engine_id}, {"error": str(error)})
        return self._record("get_prediction_uncertainty", {"engine_id": engine_id}, {
            "engine": facts["engine"], "range_low": facts["range_low_cycles"], "range_high": facts["range_high_cycles"],
            "range_is_open_ended": facts["range_is_open_ended"],
            "intended_share_inside_percent": facts["range_confidence_percent"],
            "measured_share_inside_on_test_engines_percent": facts["model"]["measured_range_coverage_percent"],
            "typical_error_flights": facts["model"]["typical_error_cycles"],
            "meaning": "About nine engines in ten fall inside a range like this and about one in ten does not. "
                       "Some engines failed sooner than the lower end, so it is not a safety margin. "
                       "If the range is open-ended, the model sees no wear yet and can only give a minimum.",
        })

    def explain_prediction(self, engine_id: int) -> dict:
        """The measurements that most influenced the estimate, and how each has changed since early life.

        Args:
            engine_id: Engine number, 1 to 100.
        """
        try:
            facts = self._facts(engine_id)
        except (KeyError, ValueError) as error:
            return self._record("explain_prediction", {"engine_id": engine_id}, {"error": str(error)})
        return self._record("explain_prediction", {"engine_id": engine_id}, {
            "engine": facts["engine"], "estimate": facts["estimate_cycles"],
            "typical_engine_estimate": facts["model_average_estimate_cycles"],
            "main_influences": [{
                "sensor_number": int(reason["sensor"].split("_")[1]), "symbol": reason["symbol"],
                "what_it_measures": reason["description"], "effect_on_estimate_flights": reason["cycles"],
                "early_life_level": reason["early_life_level"], "recent_level": reason["recent_level"],
                "unit": reason["unit"], "recent_is": reason["movement"] + " early life",
            } for reason in facts["main_reasons"]],
            "caution": "These are the readings the model relied on. They suggest a wear pattern but do not "
                       "identify a faulty part or prove a mechanical cause.",
        })

    def get_sensor_history(self, engine_id: int, sensor_number: int) -> dict:
        """How one sensor has changed over an engine's recorded flights.

        Args:
            engine_id: Engine number, 1 to 100.
            sensor_number: Sensor number, 1 to 21.
        """
        arguments = {"engine_id": engine_id, "sensor_number": sensor_number}
        name = f"sensor_{sensor_number}"
        if name not in SENSOR_INFO:
            return self._record("get_sensor_history", arguments, {"error": "Sensor numbers run from 1 to 21."})
        try:
            history = self.service.history(engine_id)
        except KeyError as error:
            return self._record("get_sensor_history", arguments, {"error": str(error)})
        if engine_id == self.selected_engine and self.cycle:
            history = history[history["cycle"] <= self.cycle]
        values = history[name]
        symbol, description, unit = SENSOR_INFO[name]
        first, last = values.head(20).mean(), values.tail(20).mean()
        return self._record("get_sensor_history", arguments, {
            "engine": f"Engine {engine_id}", "sensor_number": sensor_number, "symbol": symbol,
            "what_it_measures": description, "unit": unit, "flights_recorded": int(len(values)),
            "average_first_20_flights": round(float(first), 3), "average_last_20_flights": round(float(last), 3),
            "lowest": round(float(values.min()), 3), "highest": round(float(values.max()), 3),
            "used_by_model": name in self.service.sensors,
            "trend": "does not change" if values.nunique() <= 2 else ("has risen" if last > first else "has fallen"),
        })

    def explain_sensor(self, sensor_number: int) -> dict:
        """What a sensor measures, in plain language.

        Args:
            sensor_number: Sensor number, 1 to 21.
        """
        name = f"sensor_{sensor_number}"
        if name not in SENSOR_INFO:
            return self._record("explain_sensor", {"sensor_number": sensor_number}, {"error": "Sensor numbers run from 1 to 21."})
        symbol, description, unit = SENSOR_INFO[name]
        station = SENSOR_STATION.get(name)
        return self._record("explain_sensor", {"sensor_number": sensor_number}, {
            "sensor_number": sensor_number, "symbol": symbol, "what_it_measures": description, "unit": unit,
            "in_plain_words": plain_meaning(symbol),
            "where": STATION_NAMES.get(station, "no single location") if station else "no single location",
            "used_by_model": name in self.service.sensors,
            "naming_note": "The dataset only numbers its sensors; this name follows the NASA paper's table.",
        })

    def compare_engines(self, engine_a: int, engine_b: int) -> dict:
        """Two engines side by side: status, estimate, range and main influences.

        Args:
            engine_a: First engine number, 1 to 100.
            engine_b: Second engine number, 1 to 100.
        """
        arguments = {"engine_a": engine_a, "engine_b": engine_b}
        try:
            pair = [self._facts(engine_a), self._facts(engine_b)]
        except (KeyError, ValueError) as error:
            return self._record("compare_engines", arguments, {"error": str(error)})
        return self._record("compare_engines", arguments, {"engines": [{
            "engine": facts["engine"], "flights_recorded": facts["cycles_recorded"], "status": facts["status"]["label"],
            "estimated_flights_remaining": facts["estimate_cycles"], "range_low": facts["range_low_cycles"],
            "range_high": facts["range_high_cycles"], "range_is_open_ended": facts["range_is_open_ended"],
            "main_influences": [f"{r['description']} ({r['symbol']}): {r['cycles']:+g} flights" for r in facts["main_reasons"]],
        } for facts in pair], "note": "The model does not use an engine's age; it responds to how far readings have drifted."})

    def get_model_information(self) -> dict:
        """What the model is, how accurate it has been measured to be, and its limits."""
        service = self.service
        return self._record("get_model_information", {}, {
            "model": "XGBoost on engineered sensor features",
            "trained_on": "100 simulated engines (NASA C-MAPSS FD001 training set)",
            "typical_error_flights": service._typical_error(), "model_limit_flights": service.cap,
            "range_measured_share_inside_percent": service.settings["test_coverage_capped_truth_percent"],
            "limitations": LIMITATIONS, "glossary": GLOSSARY,
        })

    def callable_tools(self) -> list:
        return [self.get_engine_summary, self.predict_remaining_useful_life, self.get_prediction_uncertainty,
                self.explain_prediction, self.get_sensor_history, self.explain_sensor, self.compare_engines,
                self.get_model_information]
