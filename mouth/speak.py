"""Template-forward verify-then-speak (plan 4.6; E3.2 two-tag DELIBERATE).

Assertion content NEVER originates in the mouth: gate-cleared records are
rendered by the fixed template table below and inserted verbatim; the mouth
may only generate connective/social text around those immutable slots.
user-stated facts are asserted plainly; assistant-inferred facts hedged.
"""

import re

TEMPLATES = {
    "works at": "{subj} works at {obj}",
    "is employed by": "{subj} is employed by {obj}",
    "lives in": "{subj} lives in {obj}",
    "resides in": "{subj} resides in {obj}",
    "was born in": "{subj} was born in {obj}",
    "manages": "{subj} manages {obj}",
    "reports to": "{subj} reports to {obj}",
    "is married to": "{subj} is married to {obj}",
    "is a sibling of": "{subj} is a sibling of {obj}",
    "studied at": "{subj} studied at {obj}",
}
FALLBACK_TEMPLATE = "{subj} {rel} {obj}"

ABSTAIN_TEXT = "I don't have that. Want me to note it?"
RECOLLECT_TEXT = "I'm not certain from live memory — let me check my records."
ACK_TEXT = "Noted: {fact}."
ECHO_FAIL_TEXT = "I tried to note that but couldn't store it reliably, so I haven't kept it."


def render(record, provenance="user-stated"):
    """(subj, rel, obj) + provenance -> the slot-filled factual sentence."""
    subj, rel, obj = record
    core = TEMPLATES.get(rel, FALLBACK_TEMPLATE).format(subj=subj, rel=rel, obj=obj)
    if provenance == "assistant-inferred":
        return f"As far as I can infer, {core}."
    return f"{core}."


def deliberate_text(tag, candidates):
    """DELIBERATE with the E3.2 source tag.
    referential: candidates = registry entry names ("which one do you mean?")
    stored: candidates = [(record, provenance), ...] ("two facts on file")."""
    if tag == "referential":
        opts = " or ".join(candidates)
        return f"Which one do you mean: {opts}?"
    parts = " / ".join(render(rec, prov).rstrip(".") for rec, prov in candidates)
    return f"I have two different facts on file: {parts}. Which one applies?"


def speak(action, tag=None, payload=None, use_llm=False, llm_seed=None):
    """Controller action -> reply text. payload:
      ANSWER: (record, provenance); DELIBERATE: candidates per tag;
      RECOLLECT/ABSTAIN: None. With use_llm, the mouth adds a short
      connective lead-in around the immutable rendered text."""
    if action == "answer":
        fact = render(*payload) if isinstance(payload, tuple) else render(payload)
        body = fact
    elif action == "deliberate":
        body = deliberate_text(tag, payload)
    elif action == "recollect":
        body = RECOLLECT_TEXT
    else:
        body = ABSTAIN_TEXT

    if not use_llm:
        return body
    lead = verify_leadin(gen_leadin(body, llm_seed))
    return (lead + " " + body).strip() if lead else body


def gen_leadin(body, llm_seed=None):
    """The mouth's raw connective lead-in (UNVERIFIED — never emit directly)."""
    from llm import generate
    return generate(
        system=("You write a SHORT conversational lead-in (5 words or fewer) for a "
                "personal-memory assistant. You must not state any facts, names, "
                "places, times, or numbers. Just a brief social phrase."),
        user=f"The assistant is about to say: \"{body}\" Write only the lead-in.",
        max_tokens=16, temperature=0.7, seed=llm_seed,
    ).strip().strip('"')


_LEADIN_BAN = re.compile(
    r"\d|works?|lives?|born|manag|report|marri|sibling|stud|employ|schedul|"
    r"resid|mov(e|ed|ing)|job|heard|remember|talked|met|know", re.IGNORECASE)


def verify_leadin(lead):
    """verify-then-speak applied to the mouth's OWN text: connective lead-ins
    are emitted only if they carry no factual surface at all — no digits, no
    relation vocabulary, no proper nouns past the first token, <= 8 words.
    Anything suspicious is dropped (the reply is just the rendered body).
    Rationale: measured raw-lead-in leak was 92%/23% grounded/ungrounded
    (notebook entry 9) — a 3B mouth cannot be trusted with echo freedom."""
    lead = (lead or "").strip()
    if not lead or len(lead.split()) > 8:
        return ""
    if _LEADIN_BAN.search(lead):
        return ""
    for i, tok in enumerate(lead.split()):
        if i > 0 and tok[:1].isupper() and tok.split("'")[0] not in ("I",):
            return ""
    return lead
