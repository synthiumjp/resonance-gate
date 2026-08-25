#!/usr/bin/env python3
"""Entry 249: does the update axis retrieve worse than QA does, and why?

THE INCONSISTENCY. In halumem_official/eval_rgp2.py::process_user, the update
artifact is filled at line ~391 by search_memories() -> mem.recall(), the
plain BM25 tier -- and the v3 index (dense bi-encoder + cross-encoder rerank)
is not even BUILT until line ~398, for QA only. So the worst-scoring axis we
have (updating, 12.6%, 92% omission-bound) runs on the weaker retriever,
while QA gets the good one. Update queries are paraphrase-heavy, which is
exactly where lexical matching fails and dense matching wins.

This is the OFFLINE falsifier for "point update retrieval at IndexV3". No
judge, no GPU, no model calls beyond the CPU encoders retrieval already uses.

WHAT IS MEASURED, AND WHAT IT IS NOT. For each gold update point we query with
its memory_content and ask whether the retrieved set CONTAINS a fact that
covers it. Coverage is scored by token-F1 against the gold string.

  *** That is a SCREEN, not a result. ***

The token-overlap proxy is BARRED for extraction claims (ledger: it scored
garbage above correct strings and disagreed with the judge in SIGN). It is
used here only as a PAIRED comparison -- identical metric, identical gold,
identical query set, two retrievers -- to answer the ordinal question "does v3
surface more of the gold than recall() does". A win here justifies spending a
judged cycle; it does not substitute for one, and no number from this file
belongs in the ledger as an accuracy figure.

    python3 tools/update_retrieval_ab.py --user 0
"""
import argparse
import json
import os
import pathlib
import re
import sys

_P2 = "/home/jp/rg/experiments/p2"
_OFFICIAL = os.path.join(_P2, "halumem_official")
DATA = pathlib.Path.home() / "rg_private" / "halumem" / "HaluMem-Medium.jsonl"
CACHE = pathlib.Path.home() / "rg_private" / "halumem" / "qa_rgx"

_WORD = re.compile(r"[a-z0-9']+")
_STOP = {"the", "a", "an", "is", "are", "was", "were", "his", "her", "their",
         "to", "of", "and", "in", "for", "on", "with", "as", "that", "this",
         "has", "have", "had", "he", "she", "they", "it", "s"}


def toks(s):
    return {w for w in _WORD.findall((s or "").lower()) if w not in _STOP}


def f1(a, b):
    A, B = toks(a), toks(b)
    if not A or not B:
        return 0.0
    inter = len(A & B)
    if not inter:
        return 0.0
    p, r = inter / len(B), inter / len(A)
    return 2 * p * r / (p + r)


def best_cover(gold, strings):
    return max((f1(gold, s) for s in strings), default=0.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", type=int, default=0)
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--hit", type=float, default=0.5,
                    help="token-F1 at which a gold point counts as covered")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    os.environ["RG_EXTRACT_V5"] = "1"
    os.environ["RG_RETRIEVE_V3"] = "1"
    os.environ["RG_INGEST_ALL_TURNS"] = "1"
    # `llms`/`prompts` are harness-local: they live in the HaluMem eval tree,
    # which is where chain.sh cd's to before running. eval_rgp2 imports them
    # at module scope, so that directory has to be importable here too.
    _EVAL = str(pathlib.Path.home() /
                "rg_private/halumem/official/HaluMem/eval")
    for p in (_P2, _OFFICIAL, _EVAL):
        if p not in sys.path:
            sys.path.insert(0, p)

    import halumem_run as RG          # noqa: E402
    import retrieve_v3 as RV3         # noqa: E402
    import eval_rgp2 as EV            # noqa: E402
    import propositions as PR         # noqa: E402

    cache_path = str(CACHE / f"cache_u{args.user}_v5.jsonl")
    with DATA.open() as fh:
        for i, line in enumerate(fh):
            if i == args.user:
                user_data = json.loads(line)
                break

    rows = []
    for k, session in enumerate(user_data["sessions"]):
        pts = [mp for mp in session.get("memory_points", [])
               if mp.get("is_update") == "True" and mp.get("original_memories")]
        if not pts:
            continue
        mem, _ = RG.ingest_user({"sessions": user_data["sessions"][:k + 1]},
                                cache_path, min_mentions=2)
        index = RV3.IndexV3(mem)
        owner = getattr(index, "owner", None)

        for mp in pts:
            gold = mp["memory_content"]
            # ARM A: exactly what ships today
            a_strings = EV.search_memories(mem, gold, top=args.top)
            # ARM B: the same query through the QA-grade retriever
            b_facts = RV3.retrieve_facts_v3(index, gold, top_n=args.top)
            b_strings = [d.get("text") or PR.render(d, owner=owner)
                         or f"{d['attr']}: {d['value']}" for d in b_facts]

            rows.append({
                "session": k,
                "gold": gold,
                "a_cover": best_cover(gold, a_strings),
                "b_cover": best_cover(gold, b_strings),
                "a_n": len(a_strings),
                "b_n": len(b_strings),
            })
            if args.limit and len(rows) >= args.limit:
                break
        print(f"  session {k}: {len(rows)} update points scored",
              file=sys.stderr)
        if args.limit and len(rows) >= args.limit:
            break

    n = len(rows)
    if not n:
        sys.exit("no update points found")
    a_hit = sum(r["a_cover"] >= args.hit for r in rows)
    b_hit = sum(r["b_cover"] >= args.hit for r in rows)
    a_mean = sum(r["a_cover"] for r in rows) / n
    b_mean = sum(r["b_cover"] for r in rows) / n
    both = sum(r["a_cover"] >= args.hit and r["b_cover"] >= args.hit for r in rows)
    only_b = b_hit - both
    only_a = a_hit - both

    print(f"\n=== update retrieval A/B, user {args.user}, {n} gold update "
          f"points, top-{args.top} ===")
    print("  (token-F1 SCREEN, paired -- ordinal evidence only, not an "
          "accuracy number)\n")
    print(f"  A  recall()  [ships today] : mean cover {a_mean:.3f}  "
          f"covered@{args.hit} {a_hit:4d}/{n} ({100*a_hit/n:.1f}%)")
    print(f"  B  IndexV3   [proposed]    : mean cover {b_mean:.3f}  "
          f"covered@{args.hit} {b_hit:4d}/{n} ({100*b_hit/n:.1f}%)")
    print(f"\n  discordant: B-only {only_b}, A-only {only_a}")
    if a_hit:
        print(f"  ratio B/A on covered: {b_hit/a_hit:.2f}x   "
              f"(kill threshold was 1.5x)")

    # McNemar exact on the discordant pairs -- the paired test the ledger uses
    if only_a + only_b:
        from math import comb
        nd, x = only_a + only_b, min(only_a, only_b)
        pv = sum(comb(nd, i) for i in range(x + 1)) / (2 ** nd) * 2
        print(f"  McNemar exact p = {min(pv,1.0):.3g} on {nd} discordant")

    out = args.out or f"/tmp/update_ab_u{args.user}.jsonl"
    with open(out, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    print(f"\nper-point rows -> {out}")


if __name__ == "__main__":
    main()
