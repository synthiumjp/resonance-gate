"""Extraction by grammatical structure, with no model at all.

The thesis (JP): extraction should not need a powerful LLM. Grammar carries
the structure, so extract from the structure.

Two pieces of this project's own evidence say the same thing. S3c typed
relations at 98.9% against a 64.9% majority-class null using grammatical
binding and nothing else (e203). And section 4b: every extraction win came
from scope-of-input or deterministic post-processing, while prompt engineering
is 0-for-3 across ten revisions and a 1.7B/14B/24B/32B ladder.

Look at what the transformation actually is:

    source  "My name is Martin Mark, and I am a Male. I was born on
             1996-08-02, and I am now 29 years old. I currently live in
             Columbus."
    gold    User's name is Martin Mark
            Martin Mark's gender is Male
            Martin Mark's birth date is 1996-08-02
            Martin Mark's age in January 2025 is 29 years old
            Martin Mark lives in Columbus

That is a PERSON SHIFT -- first person to third -- plus a slot name. No
semantics. A model is being paid to do agreement morphology.

This is a prototype and it is deliberately shallow: regex over clause
patterns, no parser, because the point is to find out whether structure alone
reaches a useful fraction before investing in one. What it CANNOT do is
handle the discursive 96% of gold (e217) that is not a copular clause -- that
is the honest boundary and the measurement below reports it separately.

CALIBRATION WARNING. This produces gold-SHAPED output, and the token-overlap
proxy over-reads exactly that -- measured at +5.4pt for the LoRA against the
judge (e223). So coverage here is a FEASIBILITY read, not a score. Anything
this produces has to face the judge before it is believed.
"""
import re

# Clause patterns, first person, in the order they should be tried.
# Each yields (slot, value) or (None, sentence) for the verb-phrase forms.
_COP = [
    # "my <slot> is <value>"  ->  "<owner>'s <slot> is <value>"
    (re.compile(r"\bmy\s+([a-z][a-z ]{1,40}?)\s+(?:is|are)\s+([^.,;]{1,80})", re.I),
     lambda m: (m.group(1).strip().lower(), m.group(2).strip())),
    # "I am a Male" / "I am 29 years old"
    (re.compile(r"\bI\s+am\s+a[n]?\s+(male|female)\b", re.I),
     lambda m: ("gender", m.group(1).strip())),
    (re.compile(r"\bI\s+am\s+(?:now\s+)?(\d{1,3})\s+years?\s+old", re.I),
     lambda m: ("age", m.group(1) + " years old")),
    (re.compile(r"\bI\s+was\s+born\s+on\s+([0-9]{4}-[0-9]{2}-[0-9]{2})", re.I),
     lambda m: ("birth date", m.group(1))),
    (re.compile(r"\bI\s+(?:currently\s+)?live\s+in\s+([^.,;]{1,60})", re.I),
     lambda m: ("__VERB__lives in", m.group(1).strip())),
    (re.compile(r"\bI\s+(?:currently\s+)?work\s+(?:at|for)\s+([^.,;]{1,60})", re.I),
     lambda m: ("__VERB__works at", m.group(1).strip())),
    (re.compile(r"\bI\s+work\s+as\s+(?:an?\s+)?([^.,;]{1,60})", re.I),
     lambda m: ("__VERB__works as", m.group(1).strip())),
]

_NAME = re.compile(r"\bmy\s+name\s+is\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)")

_SLOT_STOP = {"basic personal information", "family", "motivation", "goal"}


def extract(text, owner=None):
    """-> list of gold-shaped propositions from ONE turn. No model call."""
    out, seen = [], set()
    o = owner or "The user"

    m = _NAME.search(text)
    if m:
        out.append(f"User's name is {m.group(1).strip()}")
        seen.add("name")

    for rx, fn in _COP:
        for m in rx.finditer(text):
            slot, val = fn(m)
            if not val or len(val.split()) > 14:
                continue
            if slot.startswith("__VERB__"):
                verb = slot[len("__VERB__"):]
                key = verb + "|" + val.lower()
                if key in seen:
                    continue
                seen.add(key)
                out.append(f"{o} {verb} {val}")
                continue
            slot = re.sub(r"\s+", " ", slot).strip()
            if slot in _SLOT_STOP or slot in seen or slot == "name":
                continue
            seen.add(slot)
            out.append(f"{o}'s {slot} is {val}")
    return out


if __name__ == "__main__":
    import collections
    import json
    import os

    STOP = set("the a an is are was were of to in on at for and or with his her "
               "their its it he she they as by from that this what which who".split())

    def toks(s):
        return {w for w in re.findall(r"[a-z0-9]+", str(s).lower())
                if w not in STOP and len(w) > 2}

    rows = [json.loads(l) for l in open(os.path.expanduser(
        "~/rg_private/halumem/HaluMem-Medium.jsonl"), encoding="utf-8")]
    for ui in (0, 1):
        u = rows[ui]
        own = None
        for s in u["sessions"]:
            for mp in s.get("memory_points", []):
                mm = re.match(r"User's name is (.+?)\s*$", mp["memory_content"])
                if mm:
                    own = mm.group(1).strip()
        ot = toks(own or "")
        per = collections.defaultdict(list)
        for si, s in enumerate(u["sessions"]):
            for t in (s.get("dialogue") or []):
                if t.get("role") != "user":
                    continue
                per[si] += extract(str(t.get("content", "")), own)
        hit = tot = 0
        cop = copn = 0
        for si, s in enumerate(u["sessions"]):
            rt = [toks(r) - ot for r in per.get(si, [])]
            for mp in s.get("memory_points", []):
                if str(mp.get("is_update")) == "True":
                    continue
                g = toks(mp["memory_content"]) - ot
                if not g:
                    continue
                tot += 1
                ok = any(len(g & r) / len(g) >= 0.5 for r in rt)
                hit += ok
                # is this gold point a copular "X's <slot> is <value>" clause?
                if re.search(r"'s [\w ]{1,30} (?:is|are) ", mp["memory_content"]):
                    copn += 1
                    cop += ok
        n = sum(len(v) for v in per.values())
        print(f"user {ui}: {n} propositions from GRAMMAR ALONE, no model")
        print(f"  gold covered @0.5   {hit}/{tot} = {hit/tot:.1%}   "
              f"({n/max(1,tot):.2f} rec/gold)")
        print(f"  of COPULAR gold     {cop}/{copn} = {cop/max(1,copn):.1%}"
              f"   <- what this prototype is actually for")
