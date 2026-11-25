"""Conversational assistant with tools.

Flow for one user message:

1. The language model (Google Gemini) receives the conversation and may call
   the tools in `tools.py`. It has no other access to engine data.
2. Its reply is checked: every number in it must appear in what the tools
   returned. A reply that fails is discarded.
3. If no key is configured, the call fails, or the check fails, a rule-based
   reply is written from the same tools instead.

The reply is shown only after the check, which is why it is not streamed word
by word: text that has not been verified should not reach the screen.
"""

import os
import re

from src.assistant.answers import answer as rule_based_answer
from src.assistant.answers import detect_intent
from src.assistant.assistant import ALWAYS_ALLOWED_NUMBERS, numbers_in
from src.assistant.knowledge import SAFETY_NOTE
from src.assistant.tools import EngineTools
from src.service.engine_service import EngineService

# The fastest model that answered reliably when tested on 2026-11-13; newer models on the same key were timing out
# or reporting high demand. Override with the GEMINI_MODEL environment variable.
DEFAULT_MODEL = "gemini-3.5-flash-lite"
# Tried next if the first model is unavailable.
BACKUP_MODEL = "gemini-3.5-flash"
REQUEST_TIMEOUT_MS = 40_000

BASE_INSTRUCTIONS = """You are the assistant inside "Predictive Intelligence", a research demonstration that \
estimates the remaining useful life of aircraft engines from sensor data. All data is the NASA C-MAPSS simulated \
benchmark, not readings from real aircraft.

The person is looking at engine {engine} on screen. Questions are about that engine unless they name another one.

You know nothing about any engine except what the tools return. Before answering anything about an engine, a \
sensor, a prediction or the model, call the relevant tools. Then explain what they returned.

Ordinary conversation is different. If the person greets you, thanks you, says goodbye, or asks who you are or \
what you can do, reply naturally and briefly, as a polite colleague would, without calling any tool and without \
stating anything about the engine. You may offer one or two examples of what they can ask. The closing reminder \
about simulated data is not needed for such replies.

Rules, which exist because an invented or over-confident statement could mislead a maintenance decision:
- State only facts and numbers that a tool returned in this turn. Copy numbers exactly. Do not calculate new \
numbers (no differences, percentages or totals of your own).
- If the tools cannot answer the question, say that this information is not available here.
- Say "flights" for cycles.
- Give the range whenever you give the estimate. If the range is open-ended, say "at least" and give no upper number.
- The range is where the true value usually falls. Never call it safe, a safety margin or an operating window.
- "Main influences" are the readings the model relied on. Never name a faulty component or state a mechanical cause.
- Status labels and suggestions are conventions of this project, not aviation standards. Offer them as things to consider.
- Never say or imply that an engine is safe, airworthy or cleared to fly, and never suggest delaying a required \
procedure. If asked, say that this decision belongs to qualified staff following approved procedures, then share \
what the model shows.
- Do not use headings. Keep the answer to a few short paragraphs; a short list is fine for influencing measurements.
- End with one sentence saying this is a research demonstration on simulated data and cannot replace approved \
maintenance procedures."""

TECHNICAL_STYLE = """
Style: write for a maintenance manager. Plain, direct sentences. Briefly explain any technical term you use."""

PLAIN_STYLE = """
Style: "Explain like I'm new to aviation" mode is ON. The reader has no background in aviation, engineering or \
statistics.
- Use everyday words. If a technical word is unavoidable, explain it in the same sentence.
- Use one everyday comparison where it helps (for example a car, a household appliance, or a health check-up).
- Say why the result matters, what the model knows, what it does not know, and what a person could consider next.
- Refer to sensors by what they measure ("a pressure reading in the compressor"), with the symbol in brackets at most once."""


# Messages that are conversation, not questions about an engine.
SMALL_TALK = re.compile(
    r"^\s*(hi+|hello+|hey+|hiya|good (morning|afternoon|evening|day)|greetings|salam|assalam[ou] ?alaikum|"
    r"thanks?( you)?( very much| a lot| so much)?|thank u|thx|ok(ay)?|great|nice|cool|good|perfect|got it|i see|"
    r"bye+|goodbye|see you|how are you( doing)?|how('s| is) it going|what'?s up|"
    r"who are you|what are you|what can you do|what do you do|how can you help( me)?|help|can you help( me)?)"
    r"[\s,!.?]*(there|assistant|please|mate|sir)?[\s!.?]*$", re.IGNORECASE)


def is_small_talk(message: str) -> bool:
    return len(message) <= 60 and bool(SMALL_TALK.match(message))


LEADING_GREETING = re.compile(
    r"^\s*(hi+|hello+|hey+|hiya|good (morning|afternoon|evening|day)|greetings|salam|assalam[ou] ?alaikum)"
    r"(\s+(there|assistant|mate|sir))?\s*[,!.]*\s+", re.IGNORECASE)


def without_greeting(message: str) -> str:
    """'Hi, is this engine healthy?' -> 'is this engine healthy?'. A greeting alone is returned unchanged."""
    if is_small_talk(message):
        return message
    rest = LEADING_GREETING.sub("", message, count=1).strip()
    return rest if rest and not is_small_talk(rest) else message


def small_talk_reply(message: str, engine_id: int) -> str:
    """A plain conversational reply, used when no language model is available."""
    text = message.lower()
    offer = (f"I can tell you about Engine {engine_id}: how healthy it looks, how many flights it may have left, "
             "what the estimate is based on, and how far to trust it.")
    if re.search(r"thank|thx", text):
        return "You're welcome. Ask me anything else about this engine whenever you like."
    if re.search(r"bye|see you", text):
        return "Goodbye. The engine's results will be here when you come back."
    if re.search(r"how are you|how('s| is) it going|what'?s up", text):
        return f"I'm working fine, thank you. {offer}"
    if re.search(r"who are you|what are you|what can you do|what do you do|help", text):
        return (f"I'm the assistant for this engine-health demonstration. {offer} You can also ask what a sensor means, "
                "or to compare this engine with another. I only use what the prediction system has worked out, "
                "and I cannot say whether an engine is safe to fly.")
    if re.search(r"^(ok(ay)?|great|nice|cool|good|perfect|got it|i see)", text.strip()):
        return "Good. Let me know if you'd like anything else explained."
    return f"Hello. {offer} What would you like to know?"


def provider_status() -> dict:
    key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    return {"provider": "Google Gemini", "model": os.environ.get("GEMINI_MODEL", DEFAULT_MODEL),
            "key_configured": bool(key),
            "fallback": "Rule-based answers written from the same tools, used when the language model is "
                        "unavailable or its answer fails the grounding check"}


def ungrounded(reply: str, tools: EngineTools, conversation: list[dict]) -> set[str]:
    """Numbers in the reply that appear in neither the tool results nor the person's own messages."""
    allowed = numbers_in(tools.evidence_text()) | ALWAYS_ALLOWED_NUMBERS
    allowed |= numbers_in(" ".join(m["content"] for m in conversation if m["role"] == "user"))
    allowed.add(f"{tools.selected_engine:g}")
    return {number for number in numbers_in(reply) if number not in allowed}


def ask_gemini(conversation: list[dict], tools: EngineTools, plain: bool) -> tuple[str | None, str]:
    """Returns (reply or None, name of the model that answered)."""
    from google import genai
    from google.genai import errors, types

    client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"),
                          http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_MS))
    instructions = BASE_INSTRUCTIONS.format(engine=tools.selected_engine) + (PLAIN_STYLE if plain else TECHNICAL_STYLE)
    contents = [types.Content(role="model" if message["role"] == "assistant" else "user",
                              parts=[types.Part(text=message["content"])]) for message in conversation]
    preferred = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
    for model in dict.fromkeys([preferred, BACKUP_MODEL]):
        tools.evidence.clear()
        try:
            # The SDK runs the tool calls the model asks for and feeds the results back until it has an answer.
            response = client.models.generate_content(
                model=model, contents=contents,
                config=types.GenerateContentConfig(system_instruction=instructions, tools=tools.callable_tools()),
            )
        except (errors.APIError, OSError, TimeoutError):
            continue      # overloaded, timed out or unreachable: try the backup model
        text = (response.text or "").strip()
        if text:
            return text, model
    return None, preferred


# ---- rule-based layer ------------------------------------------------------------------

def rule_based_reply(question: str, tools: EngineTools, plain: bool) -> str:
    """Answer from the tools without a language model."""
    text = question.lower()
    engine = tools.selected_engine

    sensor_match = re.search(r"sensor\s*#?\s*(\d{1,2})", text)
    if sensor_match and any(word in text for word in ("mean", "what is", "what's", "explain", "measure")):
        info = tools.explain_sensor(int(sensor_match.group(1)))
        if "error" in info:
            return info["error"]
        trend = tools.get_sensor_history(engine, int(sensor_match.group(1)))
        used = "The model uses it." if info["used_by_model"] else "It does not vary in this dataset, so the model does not use it."
        return (f"Sensor {info['sensor_number']} ({info['symbol']}) measures: {info['what_it_measures']}. "
                f"In plain words, it is {info['in_plain_words']}. Location: {info['where']}. {used} "
                f"On Engine {engine} it {trend['trend']}: about {trend['average_first_20_flights']} {trend['unit']} over its "
                f"first 20 flights and {trend['average_last_20_flights']} over its last 20. {info['naming_note']}\n\n{SAFETY_NOTE}")

    other = re.search(r"(?:compare|versus|vs\.?|against|with)\D{0,25}(?:engine\s*)?#?(\d{1,3})", text)
    if "compare" in text and other and int(other.group(1)) != engine:
        result = tools.compare_engines(engine, int(other.group(1)))
        if "error" in result:
            return result["error"]
        lines = []
        for item in result["engines"]:
            life = (f"at least {item['range_low']} flights" if item["range_is_open_ended"]
                    else f"{item['range_low']} to {item['range_high']} flights")
            lines.append(f"- {item['engine']}: {item['status'].lower()}; about {item['estimated_flights_remaining']} flights "
                         f"estimated, likely range {life}; {item['flights_recorded']} flights on record. "
                         f"Strongest influence: {item['main_influences'][0]}.")
        return "Side by side:\n" + "\n".join(lines) + f"\n{result['note']}\n\n{SAFETY_NOTE}"

    # Everything else: the fact-sheet templates, with the tools recorded as evidence.
    facts = tools._facts(engine)
    intent = detect_intent(question)
    tools.get_engine_summary(engine)
    if intent in ("why", "action", "inspect"):
        tools.explain_prediction(engine)
    if intent in ("life", "reliability", "consequence", "inspect", "safe"):
        tools.get_prediction_uncertainty(engine)
    reply = rule_based_answer(question, facts)
    if plain:
        reply = ("In everyday terms: an engine wears a little on every flight, like the tyres on a car. The model watches "
                 "the engine's measurements for signs of that wear and estimates how many flights are left. "
                 "A \"flight\" here means one take-off and landing.\n\n" + reply)
    return reply


def chat(service: EngineService, engine_id: int, cycle: int | None, conversation: list[dict],
         plain: bool = False, use_language_model: bool = True) -> dict:
    """Answer the latest message in a conversation about one engine."""
    # A greeting in front of a real question carries no information and made the model reply to the greeting
    # instead of looking anything up, so only the question is passed on.
    question = without_greeting(conversation[-1]["content"].strip())
    conversation = conversation[:-1] + [{**conversation[-1], "content": question}]
    tools = EngineTools(service, engine_id, cycle)
    status = provider_status()
    note = "language model switched off for this message"

    if use_language_model:
        if not status["key_configured"]:
            note = "no API key configured"
        else:
            reply, model_used = ask_gemini(conversation, tools, plain)
            if reply is None:
                pass
            elif not tools.evidence and is_small_talk(question) and not ungrounded(reply, tools, conversation):
                # Conversation needs no evidence, provided the reply states no figures about the engine.
                return {"answer": reply, "source": f"{status['provider']} ({model_used}), conversational reply",
                        "note": "", "evidence": [], "engine_id": engine_id}
            if reply is not None and not tools.evidence and not is_small_talk(question):
                # A real question was answered from thin air. Ask once more, insisting on the tools.
                nudge = {"role": "user", "content": "Please look up this engine's results with the tools first, then answer my last question."}
                reply, model_used = ask_gemini(conversation + [nudge], tools, plain)
            if reply is None:
                note = "language model unavailable"
            elif not tools.evidence:
                note = "language model answered without consulting the tools; answer discarded"
            else:
                invented = ungrounded(reply, tools, conversation)
                if not invented:
                    return {"answer": reply, "source": f"{status['provider']} ({model_used}), grounding check passed",
                            "note": "", "evidence": tools.evidence, "engine_id": engine_id}
                note = f"language model answer discarded: numbers not found in the evidence {sorted(invented)}"
            tools = EngineTools(service, engine_id, cycle)     # start the evidence list afresh for the fallback

    if is_small_talk(question):
        return {"answer": small_talk_reply(question, engine_id), "source": "rule-based, conversational reply",
                "note": note, "evidence": [], "engine_id": engine_id}
    return {"answer": rule_based_reply(question, tools, plain), "source": "rule-based", "note": note,
            "evidence": tools.evidence, "engine_id": engine_id}
