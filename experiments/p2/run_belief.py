"""p2 end-to-end: feed real gated extractions into the Bayesian belief memory.

Entry 50 built belief.py and demonstrated it on constructed scenarios. This is
the real test: does the belief STATE reproduce the validated one-shot numeric
result (7/7, fresh 0 false alarms) and lift categorical, using its own
update/contradiction logic instead of the ad-hoc RCI detector?

PIPELINE per instance (gold spans, cached extractions):
  extract  = LLM triples (extract_v2) + value-anchored + change-of-state +
             functional-attribute  -- all the evidence sources p2 built.
  gate     = each extraction gets a per-mention RELIABILITY r from its gate
             signals (grounded + ACTUAL + in-scope -> high; marginal -> low).
  slot     = (subject, attribute) via the attribute_key (numeric) / cos/functional
             attribute (categorical); value = the object (scale-normalised for
             numeric so 27:12 and 25:50 are two values of ONE slot).
  observe  = feed (slot, value, session, r) to the BeliefMemory.
  read     = a CHANGE is a slot whose belief history holds >=2 values (an update:
             old superseded; or a contradiction: concurrent rivals). This is the
             belief-native analogue of the one-shot "alert".

MEASURE: recall on knowledge-update instances, false alarms on fresh non-update.

Run: .venv/bin/python experiments/p2/run_belief.py
"""

import json
import os
import sys
import hashlib
import re
import collections

_HERE = os.path.dirname(os.path.abspath(__file__))
_R = os.path.dirname(os.path.dirname(_HERE))
for _p in (_HERE, _R, f"{_R}/substrate", f"{_R}/gate", f"{_R}/encoder", f"{_R}/mouth"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from belief import BeliefMemory
from twopath import (comparison_candidate, attribute_key, norm_subject,
                     norm_relation, distinguishing_entities)
from value_extract import extract_values
from cos_extract import extract_cos
from functional_extract import extract_functional, contains
from rci import to_scalar
from resolve import resolve_pronouns
from schema import Scope

DATA = os.path.join(_R, "data", "longmemeval_s")
CACHE = os.path.join(_HERE, "extract_cache.jsonl")

_cache = {}
for _l in open(CACHE):
    _d = json.loads(_l); _cache[_d["h"]] = [tuple(t) for t in _d["t"]]
_cf = open(CACHE, "a")


def cached(text):
    h = hashlib.sha1(text.encode("utf-8")).hexdigest()
    if h in _cache:
        return _cache[h]
    from extract_v2 import extract_triples_v2
    tr = [tuple(x) for x in extract_triples_v2(text)]
    _cache[h] = tr
    _cf.write(json.dumps({"h": h, "t": [list(x) for x in tr]}) + "\n"); _cf.flush()
    return tr


def gold(inst):
    return [(si, t["content"]) for si, s in enumerate(inst["haystack_sessions"])
            for t in s if t.get("has_answer") and t.get("role") == "user"]


# ------ slotting: map an extraction to (subject, attribute, value, reliability)

def _numeric_slot(triple, span):
    ak = attribute_key(triple)          # (subject, noun-set) for scalar objects
    if ak is None:
        return None
    sv = to_scalar(triple[2])
    if sv is None:
        return None
    # event-individuation (entry 46): a locative-destination proper noun splits
    # distinct events ("drove ... Tennessee" vs "... D.C."), so they never share
    # a slot and cannot form a spurious change.
    ak = ak + (distinguishing_entities(span, triple),)
    # value normalised to (scale, magnitude): "$1,200," and "Gucci for $1,200"
    # are the SAME value; 27:12 and 25:50 are DIFFERENT values of one slot.
    return (ak, f"{sv[1]}={sv[0]:g}")


def evidence_from_span(text, sc):
    """Yield (subject, attribute, value, reliability) for one span, from every
    evidence source. Reliability reflects the gate confidence of the source."""
    text = resolve_pronouns(text)
    ev = []
    # numeric: value-anchored (deterministic, high r) + LLM triples that gate
    for tr in [tuple(v[:3]) for v in extract_values(text)]:
        s = _numeric_slot(tr, text)
        if s:
            ev.append((s[0], s[1], 0.85))
    for tr in cached(text):
        cand, _ = comparison_candidate(text, tr)
        if cand and sc.in_scope(tr[0]) and to_scalar(tr[2]):
            s = _numeric_slot(tr, text)
            if s:
                ev.append((s[0], s[1], 0.80))
    # categorical: change-of-state (marked, high r) + functional-attribute
    for subj, attr, val, role in extract_cos(text):
        akey = (subj.lower(), "cos" if attr.startswith("cos:change") else attr)
        ev.append((akey, val.lower().strip(), 0.85))
    for subj, attr, val, vtype in extract_functional(text):
        ev.append(((subj.lower(), attr), val.lower().strip(), 0.80))
    return ev


def run_instance(inst):
    mem = BeliefMemory()
    sc = Scope()
    spans = gold(inst)
    # first pass: populate scope orbit
    for si, txt in spans:
        for tr in cached(resolve_pronouns(txt)):
            sc.observe(tr)
    for si, txt in spans:
        for slot, value, r in evidence_from_span(txt, sc):
            # slot is the full (subject, attribute) key; pass it as subject with
            # a dummy attribute so the belief dict keys on the whole slot.
            mem.observe(slot, "_", value, si, reliability=r)
    return mem


def changes(mem):
    """Belief-native change signal: a slot whose belief history holds >=2
    distinct values (one superseded another, or concurrent rivals)."""
    out = []
    for key, b in mem.slots.items():
        vals = [v for v in b.posterior() if b.n_evidence[v] > 0]
        if len(set(str(v).lower() for v in vals)) >= 2:
            hist = mem.history(key[0], key[1])
            out.append({"slot": key, "history": hist})
    return out


def main():
    d = json.load(open(DATA))
    UP = [x for x in d if x["question_type"] == "knowledge-update"]
    # updates recall
    up_hit = 0
    for inst in UP[:39]:
        if len(gold(inst)) < 2:
            continue
        mem = run_instance(inst)
        if changes(mem):
            up_hit += 1
    # fresh non-update false alarms
    others = [x for x in d if x["question_type"] != "knowledge-update" and len(gold(x)) >= 2]
    bycat = collections.defaultdict(list)
    for x in others:
        bycat[x["question_type"]].append(x)
    fresh = []
    for c, xs in sorted(bycat.items()):
        fresh += xs[:20]
    fp = 0
    fpex = []
    for inst in fresh:
        mem = run_instance(inst)
        ch = changes(mem)
        if ch:
            fp += 1
            for c in ch[:1]:
                fpex.append((inst["question_type"], c["slot"], c["history"][:3]))
    print(f"=== BELIEF MEMORY end-to-end ===")
    print(f"knowledge-update recall: {up_hit}/39   (one-shot detector: ~9 = 7 numeric + 2 categorical)")
    print(f"fresh non-update false alarms: {fp}/{len(fresh)}   (one-shot: 0)")
    for qt, slot, hist in fpex[:12]:
        print(f"   [{qt}] {slot} : {[(str(v)[:22], round(p,2)) for v,p in hist]}")


if __name__ == "__main__":
    main()
