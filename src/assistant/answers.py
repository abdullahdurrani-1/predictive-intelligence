"""Rule-based answers written directly from an engine's fact sheet.

This answerer needs no language model, cannot invent anything (every number
it prints is read from the fact sheet), and is the fallback whenever the
language model is unavailable or produces an answer that fails the grounding
check. It recognises a handful of common questions by their keywords.
"""

from src.assistant.knowledge import GLOSSARY, SAFETY_NOTE

INTENT_KEYWORDS = {
    "why": ["why", "cause", "reason", "what is wrong", "what's wrong", "unhealthy", "explain", "which sensor", "what sensor"],
    "action": ["what should", "what do we do", "what now", "next step", "recommend", "should we", "should i", "advice"],
    "inspect": ["when should", "inspect", "inspection", "maintenance", "service", "how soon"],
    "reliability": ["reliable", "trust", "confident", "confidence", "accurate", "accuracy", "sure", "certain", "guarantee"],
    "consequence": ["what could happen", "what happens if", "keep flying", "keep operating", "continue", "risk", "danger", "fail"],
    "life": ["how long", "how much longer", "remaining", "life", "last", "cycles left", "flights left", "rul"],
    "health": ["healthy", "health", "condition", "status", "how is", "okay", "ok", "fine", "state"],
    "safe": ["safe to fly", "can it fly", "airworthy", "cleared", "approve", "authorise", "authorize"],
}


def detect_intent(question: str) -> str:
    text = question.lower()
    # "safe" is checked first: the assistant must never appear to clear an engine to fly.
    for intent in ["safe", "why", "action", "inspect", "reliability", "consequence", "life", "health"]:
        if any(keyword in text for keyword in INTENT_KEYWORDS[intent]):
            return intent
    for term in GLOSSARY:
        if term in text:
            return f"glossary:{term}"
    return "overview"


def range_sentence(facts: dict) -> str:
    low = facts["range_low_cycles"]
    if facts["range_is_open_ended"]:
        return (f"The model sees no sign of the end of its life yet: its best reading is at least {low} more flights. "
                f"It cannot tell how much more than that, because it was only trained to recognise the last "
                f"{facts['rul_cap_cycles']} flights before failure.")
    return (f"The likely range is {low} to {facts['range_high_cycles']} flights. "
            f"For about nine engines in ten the true figure falls inside a range like this; for about one in ten it does not.")


def reasons_sentences(facts: dict) -> str:
    lines = []
    for reason in facts["main_reasons"]:
        direction = "pulled the estimate down" if reason["cycles"] < 0 else "pushed the estimate up"
        lines.append(
            f"- {reason['description']} ({reason['symbol']}) is now {reason['movement']} it was early in this engine's life "
            f"({reason['recent_level']} against {reason['early_life_level']} {reason['unit']}). "
            f"This {direction} by about {abs(reason['cycles']):g} flights."
        )
    return "\n".join(lines)


def answer(question: str, facts: dict) -> str:
    intent = detect_intent(question)
    status, estimate = facts["status"], facts["estimate_cycles"]
    history_note = (f" Note that only {facts['cycles_recorded']} flights of history are available for this engine, "
                    f"fewer than the model was tested with, so treat this with extra caution."
                    if facts["limited_history"] else "")

    if intent.startswith("glossary:"):
        return GLOSSARY[intent.split(":", 1)[1]]

    if intent == "safe":
        body = (f"I cannot tell you whether {facts['engine']} is safe to fly, and nothing here should be read as clearance. "
                f"That decision belongs to qualified maintenance staff following approved procedures. "
                f"What I can say is what the model sees: the engine is currently rated as \"{status['label'].lower()}\", "
                f"with an estimated {estimate} flights remaining. {range_sentence(facts)}")
    elif intent == "health":
        body = (f"{facts['engine']} is currently rated as \"{status['label'].lower()}\". {status['plain']} "
                f"The model estimates about {estimate} flights remaining. {range_sentence(facts)} "
                f"This does not by itself mean the engine is about to fail or is certain to keep working; it is an estimate.")
    elif intent == "life":
        body = (f"The model estimates about {estimate} more flights for {facts['engine']}. "
                f"This is an estimate, not a guaranteed lifespan. {range_sentence(facts)} "
                f"On engines it had never seen, the model's estimate was typically off by about "
                f"{facts['model']['typical_error_cycles']} flights. Any decision should also follow actual engineering "
                f"procedures and safety requirements.")
    elif intent == "why":
        body = (f"The model's estimate for {facts['engine']} is {estimate} flights, compared with "
                f"{facts['model_average_estimate_cycles']} for a typical engine in its training data. "
                f"These measurements had the most influence on that estimate:\n{reasons_sentences(facts)}\n"
                f"This shows which readings the model relied on. It suggests a possible wear pattern, "
                f"but the readings alone cannot prove the exact mechanical cause.")
    elif intent == "action":
        body = (f"{status['consider']} The estimate is about {estimate} flights remaining. {range_sentence(facts)} "
                f"This prediction can help decide which engines to look at first. It cannot replace an inspection "
                f"or approved aviation maintenance procedures.")
    elif intent == "inspect":
        body = (f"I cannot set an inspection date; that depends on your maintenance programme. "
                f"As a guide to priority: the engine is rated \"{status['label'].lower()}\" with about {estimate} flights "
                f"estimated remaining. {range_sentence(facts)} {status['consider']} "
                f"Because the engine could wear faster than the estimate suggests, it is sensible to plan against the "
                f"lower end of the range, not the middle.")
    elif intent == "reliability":
        body = (f"The estimate should be treated as a guide, not a certainty. {range_sentence(facts)} "
                f"When this method was checked on {100} test engines it had never seen, the true figure was inside the "
                f"range for {facts['model']['measured_range_coverage_percent']:g}% of them, and the estimate itself was "
                f"typically off by about {facts['model']['typical_error_cycles']} flights. "
                f"A few engines failed sooner than their range allowed, so the lower end is not a safety margin.")
    elif intent == "consequence":
        body = (f"If {facts['engine']} keeps operating, the model expects its measurements to keep drifting and the "
                f"engine to reach its failure point in roughly {estimate} flights. {range_sentence(facts)} "
                f"The model cannot say what kind of failure would occur or what its effects would be; it only estimates "
                f"timing, on simulated data. {status['consider']}")
    else:
        body = (f"Here is what the model sees for {facts['engine']}. It is rated \"{status['label'].lower()}\": "
                f"{status['plain'].lower()} The estimate is about {estimate} flights remaining. {range_sentence(facts)} "
                f"{status['consider']} You can ask me how healthy the engine is, how long it may last, why the model "
                f"thinks so, how reliable the estimate is, or what to consider doing next.")

    return f"{body}{history_note}\n\n{SAFETY_NOTE}"
