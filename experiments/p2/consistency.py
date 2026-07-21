"""p2 B-semantic: the LLM as a k-way JOINT-CONSISTENCY energy function.

The frontier from entry 51's discussion. Model-free linguistics could not close
categorical change because "Chicago -> the suburbs" needs world knowledge to
know the values are exclusive. The LLM HAS that knowledge. Used as a joint-
consistency energy function over an entity's fact neighbourhood -- an AUDIT over
the belief state, NOT a call on the retrieval path -- it is the requisite-
variety component Ashby says is forced for open-ended semantics, injected
exactly where forced and nowhere near read.

DESIGN, precision-first (LLM contradiction-judging is documented-unreliable:
Graphiti 1/9 on a cheap model; the 0.08 naive detector we started from). So:
  LLM PROPOSES (high recall, world knowledge) -> model-free VERIFIES.
The LLM is asked ONLY to identify, over a set of the user's own statements about
one topic across time, whether a SINGLE attribute changed (old -> new, mutually
exclusive). It is given the strict criterion from the two-judge stress protocol:
a genuine change to ONE attribute, NOT two different things sharing a type.

Measured, not asserted: recall on the categorical knowledge-update instances the
model-free path missed, precision on fresh non-update instances (must stay
silent). Validation uses the same two-independent-judge discipline afterwards.

This RELAXES the purity claim to "LLM-free RETRIEVAL; LLM at extraction AND
consistency-audit" -- an honest, Ashby-forced cost, flagged not hidden.

Judge/energy model: qwen3:14b (pinned blob), via llama-cpp on GPU.
"""

import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))

GGUF = ("/usr/share/ollama/.ollama/models/blobs/"
        "sha256-a8cc1361f3145dc01f6d77c6c82c9116b9ffe3c97b34716fe20418455876c40e")

SYSTEM = """You audit a personal memory for CHANGED FACTS. You are given several \
things ONE user said about themselves (or someone in their life) across time, in order.

Find every case where a SINGLE attribute of their life CHANGED -- they stated one \
value, then later a DIFFERENT value that cannot both be current (a genuine update or \
contradiction).

Report a change ONLY if:
- it is the SAME single attribute (their home, their employer, their most-recent trip, \
where they keep one specific thing, the day of one recurring class), AND
- the two values are MUTUALLY EXCLUSIVE (you cannot live in two cities at once; you \
cannot have one most-recent trip be both Hawaii and Paris).

Do NOT report:
- two DIFFERENT things that merely share a type (a trip to Tennessee and a different \
trip to D.C. are two trips, not one changed trip),
- values that can coexist (liking several bands, trying several restaurants, owning \
several things),
- containment (living in Chicago and living in Illinois are both true).

Reply with ONLY a JSON array, one object per genuine change:
[{"attribute": "<short name>", "old": "<earlier value>", "new": "<later value>"}]
If there is no genuine change, reply exactly: []"""

# model-free VERIFIER applied to every LLM proposal -- the precision half of the
# hybrid. Kills the exact false-alarm classes the model-free path already
# handles: identical values, containment (Chicago/Illinois), and event-
# individuation (two different trips/events sharing a type).
import re as _re
_BIG = {"illinois","california","texas","the us","usa","england","the country",
        "the city","the area","the state","abroad","overseas","nowhere",
        "not specified","unspecified","unknown"}
_EVENTY = _re.compile(r"\b(trip|vacation|holiday|getaway|visit|show|tour|event)\b", _re.I)
_PROPER = _re.compile(r"\b([A-Z][a-z]{2,})\b")

def _norm(v):
    return _re.sub(r"\s+"," ",str(v).lower()).strip(" .,!?'\"")

_GSTOP = {"a","an","the","my","our","some","of","in","at","to","for","and","or",
          "is","was","been","now","every","currently","most","recent"}

def _grounded_value(value, statements):
    """Is the value's content grounded in the source text? Content-token overlap;
    a value whose informative tokens do not appear in any statement is a
    hallucination (the 'Thursday not in text' class). This is the grounding
    construct, checked model-free -- the Competence-Gate lesson that verbalized
    output must be verified against an internal/grounded signal, not trusted."""
    toks = [t for t in _re.findall(r"[a-z0-9]+", str(value).lower())
            if len(t) > 2 and t not in _GSTOP]
    if not toks:
        return True                    # nothing checkable -> not penalised
    blob = " ".join(statements).lower()
    hit = sum(1 for t in toks if t in blob)
    return hit / len(toks) >= 0.5      # majority of content tokens present


def verify(change, statements=None):
    """True if a proposed {attribute,old,new} survives the model-free guards."""
    if statements is not None:
        if not _grounded_value(change.get("old",""), statements): return False
        if not _grounded_value(change.get("new",""), statements): return False
    o, n = _norm(change.get("old","")), _norm(change.get("new",""))
    attr = str(change.get("attribute","")).lower()
    if not o or not n or o == n:                      # identical / empty
        return False
    if o in _BIG or n in _BIG or o in n or n in o:     # containment / vague
        return False
    # EVENT-INDIVIDUATION: an "eventy" attribute (trip/tour/show) whose two
    # values are different NAMED entities is two different events, not one
    # changed value -- the entry-45/46 false-alarm class the LLM reproduces.
    if _EVENTY.search(attr):
        po, pn = set(_PROPER.findall(str(change.get("old","")))), set(_PROPER.findall(str(change.get("new",""))))
        if po and pn and po != pn:
            return False
    return True


_LLM = None


def get_llm():
    global _LLM
    if _LLM is None:
        from llama_cpp import Llama
        _LLM = Llama(GGUF, n_ctx=8192, n_gpu_layers=-1, verbose=False,
                     n_threads=os.cpu_count(), seed=0)
    return _LLM


def audit(statements):
    """statements: list of the user's utterances (strings), in time order.
    Returns a list of {attribute, old, new} the LLM believes are genuine
    single-attribute changes. This is the k-way joint-consistency energy read."""
    numbered = "\n".join(f"{i+1}. {s.strip()[:400]}" for i, s in enumerate(statements))
    out = get_llm().create_chat_completion(
        messages=[{"role": "system", "content": "/no_think " + SYSTEM},
                  {"role": "user", "content": numbered}],
        max_tokens=400, temperature=0.0)
    txt = out["choices"][0]["message"]["content"]
    txt = re.sub(r"<think>.*?</think>", "", txt, flags=re.DOTALL).strip()
    m = re.search(r"\[.*\]", txt, re.DOTALL)
    if not m:
        return []
    try:
        arr = json.loads(m.group(0))
        return [c for c in arr if isinstance(c, dict) and c.get("old") and c.get("new")]
    except Exception:
        return []
