"""p2 stress test: does the contradiction detector's 1.00 precision hold on
data it was NOT tuned on?

Entries 41-44 iterated on the FIRST 39 knowledge-update instances. Precision
measured there is optimistic. Two fresh probes:

  HELD-OUT UPDATES: knowledge-update instances the tuning never saw (index >=39).
    Tests whether recall AND precision generalise.
  FALSE-POSITIVE:   a sample of NON-update instances (temporal-reasoning,
    multi-session, single-session). These conversations are not about a
    changed fact, so the detector should stay (near-)silent. Every alert here
    is a candidate false alarm.

Runs the two-path detector on GOLD-EVIDENCE spans only (cheap), and dumps EVERY
alert with both receipt spans, for INDEPENDENT adjudication -- the precision
number must not come from the author eyeballing gold answers.

Run: .venv/bin/python experiments/p2/stress.py
"""

import json
import os
import sys
import hashlib

_HERE = os.path.dirname(os.path.abspath(__file__))
_R = os.path.dirname(os.path.dirname(_HERE))
for _p in (_HERE, _R, f"{_R}/substrate", f"{_R}/gate", f"{_R}/encoder", f"{_R}/mouth"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from twopath import run_two_path

DATA = os.path.join(_R, "data", "longmemeval_s")
CACHE = os.path.join(_HERE, "extract_cache.jsonl")
OUT = os.path.join(_HERE, "stress_alerts.jsonl")

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


def gold_spans(inst):
    return [(f"s{si}", si, t["content"])
            for si, s in enumerate(inst["haystack_sessions"])
            for t in s if t.get("has_answer") and t.get("role") == "user"]


def main():
    d = json.load(open(DATA))
    updates = [x for x in d if x["question_type"] == "knowledge-update"]
    others = [x for x in d if x["question_type"] != "knowledge-update"]

    # HELD-OUT updates: those beyond the first 39 usable that tuning saw.
    # Re-derive the "usable" ordering exactly as run_updates did (first-come,
    # >=2 gold user spans), then take everything after index 39.
    usable = [x for x in updates if len(gold_spans(x)) >= 2]
    held_updates = usable[39:]

    # FALSE-POSITIVE sample: 60 non-update instances with >=2 gold spans,
    # deterministically (no RNG in this env); spread across their categories.
    fp = [x for x in others if len(gold_spans(x)) >= 2]
    import collections
    bycat = collections.defaultdict(list)
    for x in fp:
        bycat[x["question_type"]].append(x)
    fp_sample = []
    for cat, xs in sorted(bycat.items()):
        fp_sample += xs[:15]

    n_alerts = 0
    with open(OUT, "w") as out:
        for arm, insts in (("held_update", held_updates), ("non_update", fp_sample)):
            for inst in insts:
                gs = gold_spans(inst)
                spans = [(sid, si, txt) for sid, si, txt in gs]
                _, res = run_two_path(spans, cached)
                span_text = {sid: txt for sid, si, txt in gs}
                for a in res["alerts"]:
                    n_alerts += 1
                    out.write(json.dumps({
                        "arm": arm, "question_id": inst["question_id"],
                        "question": inst["question"], "gold_answer": inst["answer"],
                        "question_type": inst["question_type"],
                        "obj_a": a["obj_a"], "obj_b": a["obj_b"],
                        "attribute_key": str(a["key"]),
                        "receipt_a_session": a.get("session_a"),
                        "receipt_b_session": a.get("session_b"),
                        "receipt_a_text": span_text.get(a.get("receipt_a"), ""),
                        "receipt_b_text": span_text.get(a.get("receipt_b"), ""),
                    }) + "\n")
            print(f"  {arm}: {len(insts)} instances processed", flush=True)

    alerts = [json.loads(l) for l in open(OUT)]
    print(f"\nTOTAL ALERTS: {n_alerts}")
    for arm in ("held_update", "non_update"):
        aa = [a for a in alerts if a["arm"] == arm]
        insts = len(set(a["question_id"] for a in aa))
        print(f"  {arm}: {len(aa)} alerts across {insts} instances")
    print(f"\n-> {OUT} (for independent adjudication)")


if __name__ == "__main__":
    main()
