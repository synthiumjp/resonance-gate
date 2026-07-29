"""Deterministic retrieval-variant lab (no judge, no GPU, seconds per sweep).

Measures, for each ranking variant, on real-gold dev questions:
  recall@k   -- some retrieved fact VALUE contains >=50% of gold content tokens
                (same containment criterion as oracle.gold_in_store, restricted
                to the top-k retrieved facts)
  rank stats -- best rank of a gold-bearing fact (median, top-5 rate, top-10)

Rationale: recall@120 is near its k=250 saturation ceiling (~90%), so variants
are judged primarily on RANK (how early the gold appears -- what the composer
actually benefits from) and on recall at SMALL k, not on recall@120 alone.

Usage:
  recall_lab.py --users 10-12 [--k 120] [--variants base,porter,...]
"""
import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import halumem_run as HR
import retrieve as RV
from wire import _tokens
from oracle import _NO_INFO_RX
from dev_set import _load_users, _parse_users_arg, _cache_path, _cache_complete

CACHE_TEMPLATE = "~/rg_private/halumem/dev/cache_u{i}_v5_14b.jsonl"


def rank_variant(name, mem, question, index):
    """Return facts ranked by the named variant (list of fact dicts)."""
    facts, docs, idf, avgdl = index
    qt = RV.query_tokens(question)
    scored = []
    for j, t in enumerate(docs):
        inter = qt & t
        if not inter:
            continue
        dl = len(t)
        s = sum(idf.get(x, 0.0) * ((RV.K1 + 1) /
                (1 + RV.K1 * (1 - RV.B + RV.B * dl / avgdl)))
                for x in inter)
        scored.append((s, facts[j]["n_mentions"], j))
    scored.sort(key=lambda z: (-z[0], -z[1]))
    return [facts[j] for _, _, j in scored]


VARIANTS = {"base": rank_variant}


def score(users_arg, k, variants):
    users = _load_users()
    per_variant = {v: {"cov": 0, "tot": 0, "ranks": []} for v in variants}
    for uidx in _parse_users_arg(users_arg):
        user = users[uidx]
        cpath = _cache_path(uidx, CACHE_TEMPLATE)
        complete, have, total = _cache_complete(user, cpath)
        if not complete:
            print(f"user {uidx}: cache incomplete ({have}/{total}) -- skip")
            continue
        mem, _ = HR.ingest_user(user, cpath)
        index = RV.build_index(mem)
        qs = [q for s in user["sessions"] for q in s.get("questions", [])]
        for q in qs:
            gold = str(q.get("answer", "")).strip()
            if not gold or _NO_INFO_RX.search(gold):
                continue
            gt = _tokens(gold)
            if not gt:
                continue
            for v in variants:
                st = per_variant[v]
                st["tot"] += 1
                ranked = VARIANTS[v](v, mem, q["question"], index)
                best = None
                for r, d in enumerate(ranked[:k]):
                    if len(gt & _tokens(d["value"])) / len(gt) >= 0.5:
                        best = r
                        break
                if best is not None:
                    st["cov"] += 1
                    st["ranks"].append(best)
    print(f"\n=== recall lab, k={k} ===")
    for v in variants:
        st = per_variant[v]
        rs = sorted(st["ranks"])
        med = rs[len(rs) // 2] if rs else -1
        t5 = sum(1 for r in rs if r < 5)
        t10 = sum(1 for r in rs if r < 10)
        n = max(st["tot"], 1)
        print(f"  {v:12} recall@{k} {100*st['cov']/n:5.1f}% ({st['cov']}/{st['tot']})  "
              f"gold-rank median {med}  top5 {100*t5/n:5.1f}%  top10 {100*t10/n:5.1f}%")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--users", default="10-12")
    ap.add_argument("--k", type=int, default=RV.DEFAULT_K)
    ap.add_argument("--variants", default="base")
    args = ap.parse_args()
    score(args.users, args.k, args.variants.split(","))


if __name__ == "__main__":
    main()
