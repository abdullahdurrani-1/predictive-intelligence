"""The question-answering assistant.

Two layers:

1. A language model (Claude) writes a natural answer, but only from the fact
   sheet it is handed. Its answer is then checked: every number it states must
   appear in the fact sheet.
2. If no API credential is configured, the call fails, the model declines, or
   the check fails, the rule-based answerer in `answers.py` is used instead.

Either way the reply records which layer produced it.
"""

import json
import os
import re

from src.assistant.answers import answer as rule_based_answer
from src.assistant.knowledge import SAFETY_NOTE

MODEL = "claude-opus-5-5"

SYSTEM_PROMPT = """You are the explanation assistant inside "Predictive Intelligence", a research demonstration \
that estimates the remaining useful life of aircraft engines from sensor data. The data is the NASA C-MAPSS \
simulated benchmark, not readings from real aircraft.

Your reader is a maintenance manager or an ordinary person with no background in machine learning, statistics \
or aerospace engineering. They need to understand what the model found, how far to trust it, and what they \
might consider doing. Write the way a careful engineer would explain it to a colleague from another department: \
plain words, short paragraphs, no jargon. Say "flights" for cycles. If you must use a technical term, explain it \
in the same sentence.

Each request gives you a FACT SHEET for one engine, produced by the prediction system, followed by the \
person's question. The fact sheet is your only source of information about the engine.

Grounding rules. These exist because a confident, invented number about an engine could mislead a maintenance \
decision:
- State only engine facts that appear in the fact sheet. Never estimate, extrapolate or round to a different \
value. Copy numbers exactly as given.
- If the question asks for something the fact sheet does not contain, say plainly that this information is \
not available here.
- The estimate is a prediction, not a guarantee. When you give the estimate, give the range with it.
- If "range_is_open_ended" is true, say "at least <range_low_cycles> flights" and explain that the model cannot \
see further than that. Do not quote an upper number.
- The range covers about nine engines in ten. Never call it a safe operating window; some engines fail sooner \
than the lower end.
- "main_reasons" lists the measurements that most influenced the model. Describe them as what the model relied \
on. They do not identify the mechanical cause, and you must not name a faulty component.
- The status label and the suggested consideration are conventions of this project, not aviation standards. \
Offer them as things to consider.
- Never state or imply that an engine is safe to fly, cleared, or airworthy, and never suggest delaying or \
skipping a required procedure. Those decisions belong to qualified staff following approved procedures. \
If asked, say so directly and then share what the model does show.

Answer the question that was asked, in a few short paragraphs at most. Do not add headings or bullet lists \
unless listing the influencing measurements. End with one sentence reminding the reader that this is a \
research demonstration on simulated data and cannot replace approved maintenance procedures."""

# Numbers that may appear in an answer without being in the fact sheet
# ("one engine in ten", "nine in ten", "90%").
ALWAYS_ALLOWED_NUMBERS = {"1", "9", "10", "90", "100"}


def numbers_in(text: str) -> set[str]:
    """Every number in a piece of text, normalised so that 21, 21.0 and 21.00 compare equal."""
    found = set()
    for match in re.findall(r"\d+(?:\.\d+)?", text.replace(",", "")):
        found.add(f"{float(match):g}")
    return found


def ungrounded_numbers(reply: str, facts: dict) -> set[str]:
    """Numbers stated in the reply that cannot be traced to the fact sheet."""
    allowed = numbers_in(json.dumps(facts)) | ALWAYS_ALLOWED_NUMBERS
    # Sensor contributions and changes may reasonably be quoted without their sign.
    return {number for number in numbers_in(reply) if number not in allowed}


def credentials_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def ask_language_model(question: str, facts: dict) -> str | None:
    """Ask Claude to answer from the fact sheet. Returns None if no usable answer came back."""
    import anthropic

    client = anthropic.Anthropic()
    try:
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            output_config={"effort": "medium"},
            # If a safety classifier declines the request, let the API retry on its default fallback model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            # The instructions never change, so they can be cached across questions.
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{
                "role": "user",
                "content": f"FACT SHEET\n{json.dumps(facts, indent=1, sort_keys=True)}\n\nQUESTION\n{question}",
            }],
        )
    except anthropic.AuthenticationError:
        return None
    except anthropic.RateLimitError:
        return None
    except anthropic.APIStatusError:
        return None
    except anthropic.APIConnectionError:
        return None

    if response.stop_reason in ("refusal", "max_tokens"):
        return None
    text = "".join(block.text for block in response.content if block.type == "text").strip()
    return text or None


def answer_question(question: str, facts: dict, use_language_model: bool = True) -> dict:
    """Answer a question about one engine. Always returns an answer and says how it was produced."""
    question = question.strip()
    if not question:
        return {"answer": "Please ask a question about this engine.", "source": "rule-based", "note": "empty question"}

    note = "language model not requested"
    if use_language_model:
        if not credentials_available():
            note = "no API credential configured"
        else:
            reply = ask_language_model(question, facts)
            if reply is None:
                note = "language model unavailable or declined"
            else:
                invented = ungrounded_numbers(reply, facts)
                if not invented:
                    return {"answer": reply, "source": "language model (grounding check passed)", "note": ""}
                note = f"language model answer rejected: numbers not in the fact sheet {sorted(invented)}"

    return {"answer": rule_based_answer(question, facts), "source": "rule-based", "note": note}


__all__ = ["answer_question", "ungrounded_numbers", "SAFETY_NOTE"]
