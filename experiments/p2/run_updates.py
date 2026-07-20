"""p2: can we see a knowledge update at all?

Contradiction disclosure is the product claim, and across 165 facts from 10
random users it fired ONCE. Before improving the matcher it is worth asking a
cheaper question: on instances that contain an update BY CONSTRUCTION, does
the pipeline even extract BOTH SIDES of it?

LongMemEval's knowledge-update instances mark their gold-evidence turns
(`has_answer`), and those turns are where the old and new values are stated.
So this extracts from the GOLD SPANS ONLY — two or three turns per instance
rather than ~250 — which makes it minutes instead of hours, and it measures
the ceiling: if both sides are not extractable, no matching improvement can
help and the claim is not demonstrable on this data.

Reports, per instance:
  - how many gold spans there are
  - what the pipeline extracts from each, after gate + scope
  - whether two extracted facts share a subject (the matchable case)
  - whether they share subject AND relation (what the current detector needs)

Run: .venv/bin/python experiments/p2/run_updates.py [n_instances]
"""

import json
import os
import sys
from collections import defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
_R = os.path.dirname(os.path.dirname(_HERE))
for _p in (_HERE, _R, f"{_R}/substrate", f"{_R}/gate", f"{_R}/encoder", f"{_R}/mouth"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ingest import Ingestor, fact_key
from schema import Scope

DATA = os.path.join(_R, "data", "longmemeval_s")
OUT = os.path.join(_HERE, "updates.json")
_V2OUT = os.path.join(_HERE, "updates_v2.json")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    n = int(args[0]) if args else 40
    if "--v2" in sys.argv:
        from extract_v2 import extract_triples_v2 as extract_triples
        print("EXTRACTOR: v2 (experiments/p2/extract_v2.py)")
    else:
        from write_path import extract_triples
        print("EXTRACTOR: v1 (frozen write_path.EXTRACT_SYSTEM)")

    d = [x for x in json.load(open(DATA)) if x["question_type"] == "knowledge-update"]
    print(f"knowledge-update instances available: {len(d)}; using {min(n, len(d))}\n")

    rows = []
    for inst in d[:n]:
        gold = [(si, t.get("content", ""))
                for si, sess in enumerate(inst["haystack_sessions"])
                for t in sess if t.get("has_answer") and t.get("role") == "user"]
        if len(gold) < 2:
            rows.append({"instance": inst["question_id"], "n_gold": len(gold),
                         "skipped": "fewer than 2 gold user turns"})
            continue

        ing = Ingestor(extractor=extract_triples)
        sc = Scope()
        per_span = []
        for si, text in gold:
            recs = ing.ingest(text, session_id=si)
            for r in recs:
                sc.observe(r.triple)
            per_span.append([r.triple for r in recs])

        allf = [t for grp in per_span for t in grp]
        in_scope = [t for t in allf if sc.in_scope(t[0])]
        by_subj = defaultdict(set)
        by_sr = defaultdict(set)
        for t in in_scope:
            k = fact_key(t)
            by_subj[k[0]].add(k[2])
            by_sr[(k[0], k[1])].add(k[2])
        rows.append({
            "instance": inst["question_id"], "question": inst["question"][:120],
            "answer": str(inst.get("answer"))[:80],
            "n_gold": len(gold),
            "extracted": len(allf), "in_scope": len(in_scope),
            "shared_subject_multi_object": sum(1 for v in by_subj.values() if len(v) > 1),
            "shared_subj_rel_multi_object": sum(1 for v in by_sr.values() if len(v) > 1),
            "facts": [list(t) for t in in_scope][:8],
        })
        r = rows[-1]
        print(f"  {r['instance'][:18]:<18} gold={r['n_gold']} extracted={r['extracted']:>2} "
              f"in_scope={r['in_scope']:>2} sharedSubj={r['shared_subject_multi_object']} "
              f"sharedSubjRel={r['shared_subj_rel_multi_object']}", flush=True)

    json.dump(rows, open(_V2OUT if "--v2" in sys.argv else OUT, "w"), indent=1)
    ok = [r for r in rows if not r.get("skipped")]
    print(f"\n=== CEILING ON THE PRODUCT CLAIM ({len(ok)} usable instances) ===")
    print(f"  instances where any fact survived gate+scope:        "
          f"{sum(1 for r in ok if r['in_scope'] > 0)}/{len(ok)}")
    print(f"  instances with 2+ facts sharing a SUBJECT:           "
          f"{sum(1 for r in ok if r['shared_subject_multi_object'] > 0)}/{len(ok)}")
    print(f"  instances with 2+ facts sharing SUBJECT AND RELATION:"
          f" {sum(1 for r in ok if r['shared_subj_rel_multi_object'] > 0)}/{len(ok)}"
          f"   <- what the current detector requires")
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
