"""p2: does corroboration do any work?

Two questions, neither of which needs new hand labels — LongMemEval marks its
own gold-evidence turns (`has_answer`).

  Q1 VIABILITY.  What fraction of distinct facts are ever independently
     restated? If it is ~0 the PROMOTED tier never fires and the whole
     corroboration design is dead weight.
  Q2 UTILITY.    Do promoted facts land disproportionately on gold-evidence
     turns? This is the Kang et al. (arXiv:2606.10616) construct — is the
     retained set the evidence a later query actually needs — measured against
     the dataset's own ground truth rather than my labels. Their
     Generative-Agents importance baseline scores F1 0.020-0.027; corroboration
     is the cheaper alternative and this asks whether it beats that construct
     at all.

Run on the FULL haystack (`longmemeval_s`, ~50 sessions per user), not the
oracle split: oracle is pruned to evidence sessions, so 176 of its 500
instances have a single session and any corroboration rate measured there
would be an artefact of the pruning.

One Ingestor per instance — each instance is one user, and facts must never
corroborate across users.

Run: .venv/bin/python experiments/p2/run_corroboration.py [n_instances]
"""

import json
import os
import sys
import time
from collections import defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
_R = os.path.dirname(os.path.dirname(_HERE))
for _p in (_HERE, _R, f"{_R}/substrate", f"{_R}/gate", f"{_R}/encoder", f"{_R}/mouth"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ingest import Ingestor, fact_key
from gate import PROMOTED, PROVISIONAL

DATA = os.path.join(_R, "data", "longmemeval_s")
OUT = os.path.join(_HERE, "corroboration.json")
SEED_ORDER = 20260726


def main():
    n_inst = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    from write_path import extract_triples
    import random

    d = json.load(open(DATA))
    rng = random.Random(SEED_ORDER)
    # sample across question types so knowledge-update instances are included
    idx = list(range(len(d)))
    rng.shuffle(idx)
    chosen = idx[:n_inst]

    rows, t0 = [], time.time()
    for n, ii in enumerate(chosen):
        inst = d[ii]
        ing = Ingestor(extractor=extract_triples)
        gold_spans = set()
        n_turns = 0
        for si, sess in enumerate(inst["haystack_sessions"]):
            for t in sess:
                if t.get("role") != "user":
                    continue
                sid = f"i{ii}_s{si}_t{n_turns}"
                if t.get("has_answer"):
                    gold_spans.add(sid)
                ing.ingest(t.get("content", ""), session_id=si, span_id=sid)
                n_turns += 1
        # per-fact aggregation
        facts = defaultdict(list)
        for r in ing.records:
            facts[fact_key(r.triple)].append(r)
        rec = {
            "instance": ii, "question_type": inst["question_type"],
            "n_sessions": len(inst["haystack_sessions"]), "n_user_turns": n_turns,
            "n_records": len(ing.records), "n_distinct_facts": len(facts),
            "n_gold_spans": len(gold_spans),
            "corroborated_facts": sum(1 for v in facts.values()
                                      if any(r.corroborations >= 1 for r in v)),
            "promoted_records": sum(1 for r in ing.records if r.tier == PROMOTED),
            "modality_counts": dict(_count(r.modality for r in ing.records)),
            # gold overlap: did a record come from a gold-evidence span?
            "gold_hits_all": sum(1 for r in ing.records if r.span_id in gold_spans),
            "gold_hits_promoted": sum(1 for r in ing.records
                                      if r.tier == PROMOTED and r.span_id in gold_spans),
            "gold_hits_provisional": sum(1 for r in ing.records
                                         if r.tier == PROVISIONAL and r.span_id in gold_spans),
            "n_provisional": sum(1 for r in ing.records if r.tier == PROVISIONAL),
        }
        rows.append(rec)
        el = time.time() - t0
        print(f"  [{n+1}/{n_inst}] inst {ii} ({inst['question_type']}): "
              f"{n_turns} turns -> {len(ing.records)} records, "
              f"{rec['corroborated_facts']}/{len(facts)} facts corroborated, "
              f"{rec['promoted_records']} promoted  [{el/60:.1f}m]", flush=True)
        with open(OUT, "w") as f:
            json.dump(rows, f, indent=1)
    summarise(rows)


def _count(it):
    c = defaultdict(int)
    for x in it:
        c[x] += 1
    return c


def summarise(rows):
    T = lambda k: sum(r[k] for r in rows)
    print("\n=== Q1 VIABILITY ===")
    print(f"  user turns ingested      {T('n_user_turns')}")
    print(f"  triple records kept      {T('n_records')}")
    print(f"  distinct facts           {T('n_distinct_facts')}")
    cf, df = T('corroborated_facts'), T('n_distinct_facts')
    print(f"  independently restated   {cf}/{df} = {cf/df if df else float('nan'):.3f}")
    print(f"  promoted records         {T('promoted_records')}")

    print("\n=== Q2 UTILITY (gold-evidence enrichment) ===")
    base = T('gold_hits_all') / T('n_records') if T('n_records') else float('nan')
    pro = T('gold_hits_promoted') / T('promoted_records') if T('promoted_records') else float('nan')
    prov = T('gold_hits_provisional') / T('n_provisional') if T('n_provisional') else float('nan')
    print(f"  P(from gold span | any record)         {base:.4f}")
    print(f"  P(from gold span | PROVISIONAL)        {prov:.4f}")
    print(f"  P(from gold span | PROMOTED)           {pro:.4f}")
    if base and base == base:
        print(f"  enrichment, promoted vs all            {pro/base:.2f}x")
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
