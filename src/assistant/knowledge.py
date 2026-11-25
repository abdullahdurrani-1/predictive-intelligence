"""Documented rules and wording the assistant is allowed to use.

IMPORTANT: the status bands and suggested actions below are *project
conventions for this demonstration*. They are not aviation regulations,
manufacturer limits or approved maintenance procedures, and the assistant
must never present them as such.
"""

# Status bands, checked in order. An engine falls into the first band it matches.
#   estimate  = the model's RUL estimate in cycles
#   low       = lower end of the 90% range
STATUS_BANDS = [
    {
        "key": "near_end_of_predicted_life",
        "label": "Close to the end of its predicted life",
        "applies": lambda estimate, low, open_ended: estimate <= 30 or low <= 15,
        "plain": "Several measurements have moved well away from where they were when this engine was new.",
        "consider": "Consider prioritising this engine for review by the maintenance team now.",
    },
    {
        "key": "advanced_wear",
        "label": "Showing clear signs of wear",
        "applies": lambda estimate, low, open_ended: estimate <= 60,
        "plain": "The engine's measurements have drifted clearly from their early-life levels.",
        "consider": "Consider planning an inspection and watching this engine more closely.",
    },
    {
        "key": "early_wear",
        "label": "Showing early signs of wear",
        "applies": lambda estimate, low, open_ended: estimate < 100 or not open_ended,
        "plain": "Some measurements have started to move away from the patterns seen in healthier engines.",
        "consider": "Consider reviewing this engine at the next planned check and keeping it under observation.",
    },
    {
        "key": "no_measurable_wear",
        "label": "No measurable wear yet",
        "applies": lambda estimate, low, open_ended: True,
        "plain": "The engine's measurements are still close to where they were when it was new.",
        "consider": "Routine monitoring appears sufficient on this evidence.",
    },
]


def status_for(estimate: int, low: int, open_ended: bool) -> dict:
    for band in STATUS_BANDS:
        if band["applies"](estimate, low, open_ended):
            return {"key": band["key"], "label": band["label"], "plain": band["plain"], "consider": band["consider"],
                    "basis": "project demonstration rule, not an aviation standard"}
    raise RuntimeError("status bands must end with a catch-all")


LIMITATIONS = [
    "The data is simulated benchmark data, not readings from a real aircraft.",
    "The estimate is a statistical prediction, not a guaranteed lifespan.",
    "About one engine in ten is expected to fall outside the stated range.",
    "The model can explain which measurements influenced its estimate, but cannot identify the mechanical cause.",
    "It cannot authorise an engine to fly or replace approved maintenance procedures.",
]

SAFETY_NOTE = (
    "This is a research demonstration on simulated data. It can help prioritise attention, "
    "but decisions must follow approved maintenance procedures and qualified engineering judgement."
)

# Everyday explanations of terms a non-specialist may ask about.
GLOSSARY = {
    "cycle": "One cycle is one flight: a take-off, cruise and landing.",
    "remaining useful life": "Remaining useful life is the number of flights the model estimates the engine can still make before it would reach its failure point in the simulation.",
    "range": "The range is where the true answer usually falls. For about nine engines in ten the real remaining life is inside it; for about one in ten it is not.",
    "sensor": "A sensor is a measuring device on the engine, recording things like temperature, pressure and rotation speed.",
}
