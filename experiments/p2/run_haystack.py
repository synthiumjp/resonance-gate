"""p2: ingest full haystack users and dump per-fact survival records.

Extraction is the expensive step (~1s/turn), so this runs it ONCE and dumps
everything needed to compute strength offline. Survival rules can then be
iterated without touching the GPU again.

Per user (= one LongMemEval instance, ~50 sessions):
  for each session, in order:
    for each user turn:
      extract + gate           -> admitted records
      test PRIOR facts against this span   (activation / contradiction)
      register this span's facts

A span only tests facts registered in EARLIER sessions — a fact cannot
corroborate itself, and same-session restatement is not independent evidence.

Output: haystack_facts.jsonl, one row per distinct fact per user, carrying the
static evidence, the activation/contradiction counts, exposure (how many
sessions the user had after the fact first appeared), and whether the fact came
from a gold-evidence span.

Run: .venv/bin/python experiments/p2/run_haystack.py [n_instances]
"""

import json
import os
import random
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_R = os.path.dirname(os.path.dirname(_HERE))
for _p in (_HERE, _R, f"{_R}/substrate", f"{_R}/gate", f"{_R}/encoder", f"{_R}/mouth"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ingest import Ingestor, fact_key
from strength import SurvivalIndex, static_evidence

DATA = os.path.join(_R, "data", "longmemeval_s")
OUT = os.path.join(_HERE, "haystack_facts.jsonl")
SEED = 20260726


def main():
    n_inst = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    from write_path import extract_triples

    d = json.load(open(DATA))
    rng = random.Random(SEED)
    idx = list(range(len(d)))
    rng.shuffle(idx)

    out = open(OUT, "w")
    t0 = time.time()
    for n, ii in enumerate(idx[:n_inst]):
        inst = d[ii]
        ing = Ingestor(extractor=extract_triples)
        surv = SurvivalIndex()
        gold_spans, n_turns = set(), 0
        n_sessions = len(inst["haystack_sessions"])

        for si, sess in enumerate(inst["haystack_sessions"]):
            for t in sess:
                if t.get("role") != "user":
                    continue
                text = t.get("content", "")
                sid = f"i{ii}_s{si}_t{n_turns}"
                if t.get("has_answer"):
                    gold_spans.add(sid)
                recs = ing.ingest(text, session_id=si, span_id=sid)
                # this span tests facts registered in EARLIER sessions
                surv.observe_span(text, si, [r.triple for r in recs])
                for r in recs:
                    surv.observe_fact(fact_key(r.triple), r.triple, text, si,
                                      static_evidence(text, r.triple))
                n_turns += 1

        first_span = {}
        for r in ing.records:
            first_span.setdefault(fact_key(r.triple), r)
        for key, f in surv.facts.items():
            rec = first_span.get(key)
            sc = surv.score(key, current_session=n_sessions - 1)
            out.write(json.dumps({
                "instance": ii, "question_type": inst["question_type"],
                "fact_key": list(key), "triple": list(f["triple"]),
                "first_session": f["first_session"], "n_sessions": n_sessions,
                "exposure": n_sessions - 1 - f["first_session"],
                "activations": sc["activations"],
                "contradictions": sc["contradictions"],
                "dormancy": sc["dormancy"], "modality": sc["modality"],
                "ev": f["ev"], "strength": sc["strength"],
                "span_id": rec.span_id if rec else None,
                "span": ing.spans[rec.span_id]["text"][:600] if rec else None,
                "from_gold_span": bool(rec and rec.span_id in gold_spans),
            }) + "\n")
        out.flush()
        el = (time.time() - t0) / 60
        act = sum(1 for f in surv.facts.values() if f["activations"])
        print(f"  [{n+1}/{n_inst}] inst {ii} {inst['question_type']}: "
              f"{n_sessions} sessions, {n_turns} turns -> {len(surv.facts)} facts, "
              f"{act} activated, "
              f"{sum(1 for f in surv.facts.values() if f['contradictions'])} contradicted "
              f"[{el:.1f}m]", flush=True)
    out.close()
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
