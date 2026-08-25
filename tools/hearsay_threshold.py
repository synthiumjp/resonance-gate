#!/usr/bin/env python3
"""Entry 249: pick the hearsay relevance floor from the score distribution.

The first cut of labeled hearsay appended 3 lines to 155 of 164 questions --
every question for which the store held ANY hearsay at all. That is because
retrieve_facts_v3 returns top_n by RANK, unconditionally: it has no way to say
"nothing here is on topic". Fine for the main fact pool, wrong for an optional
side channel.

This dumps the cross-encoder logits for the top hearsay candidate per question
alongside the top MAIN-fact logit for the same question, so the floor can be
read off real data instead of guessed. The main-fact score is the reference:
it is what "this retrieval is on topic" looks like for this encoder on this
corpus.

    python3 tools/hearsay_threshold.py --user 0
"""
import argparse
import json
import os
import pathlib
import sys

_P2 = "/home/jp/rg/experiments/p2"
_OFFICIAL = os.path.join(_P2, "halumem_official")
DATA = pathlib.Path.home() / "rg_private" / "halumem" / "HaluMem-Medium.jsonl"
CACHE = pathlib.Path.home() / "rg_private" / "halumem" / "qa_rgx"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", type=int, default=0)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    os.environ["RG_EXTRACT_V5"] = "1"
    os.environ["RG_RETRIEVE_V3"] = "1"
    os.environ["RG_INGEST_ALL_TURNS"] = "1"
    os.environ["RG_HEARSAY"] = "1"
    for p in (_P2, _OFFICIAL):
        if p not in sys.path:
            sys.path.insert(0, p)

    import halumem_run as RG      # noqa: E402
    import retrieve_v3 as RV3     # noqa: E402

    cache_path = str(CACHE / f"cache_u{args.user}_v5.jsonl")
    with DATA.open() as fh:
        for i, line in enumerate(fh):
            if i == args.user:
                user_data = json.loads(line)
                break

    rows = []
    for k, session in enumerate(user_data["sessions"]):
        questions = session.get("questions") or []
        if not questions or session.get("is_generated_qa_session", False):
            continue
        mem, _ = RG.ingest_user({"sessions": user_data["sessions"][:k + 1]},
                                cache_path, min_mentions=2)
        index = RV3.IndexV3(mem)
        hs_index = getattr(index, "hearsay", None)
        for q in questions:
            question = q["question"]
            main = RV3.retrieve_facts_v3(index, question, top_n=5,
                                         with_scores=True)
            hs = ([] if hs_index is None else
                  RV3.retrieve_facts_v3(hs_index, question, top_n=5,
                                        with_scores=True))
            rows.append({
                "session": k,
                "question": question,
                "main_top": main[0][1] if main else None,
                "hearsay_scores": [s for _, s in hs],
                "hearsay_texts": [d.get("text") or f"{d['attr']}: {d['value']}"
                                  for d, _ in hs[:3]],
            })
        print(f"  session {k}: {len(rows)} questions scored", file=sys.stderr)

    out = args.out or f"/tmp/hearsay_scores_u{args.user}.jsonl"
    with open(out, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")

    mains = sorted(r["main_top"] for r in rows if r["main_top"] is not None)
    tops = sorted(r["hearsay_scores"][0] for r in rows if r["hearsay_scores"])

    def pct(xs, p):
        return xs[min(int(len(xs) * p), len(xs) - 1)] if xs else float("nan")

    print(f"\n=== cross-encoder logits, user {args.user}, {len(rows)} questions ===")
    print(f"{'':22s}{'p10':>8s}{'p25':>8s}{'p50':>8s}{'p75':>8s}{'p90':>8s}")
    for name, xs in (("top MAIN fact", mains), ("top HEARSAY fact", tops)):
        print(f"{name:22s}" + "".join(f"{pct(xs, p):8.2f}"
                                      for p in (.1, .25, .5, .75, .9)))
    print(f"\nhearsay available on {len(tops)}/{len(rows)} questions")
    for thr in (-8, -6, -4, -2, 0, 2, 4):
        n = sum(1 for t in tops if t >= thr)
        print(f"  floor {thr:+3d}: hearsay appended on {n:4d}/{len(rows)} "
              f"questions ({100*n/len(rows):5.1f}%)")
    print(f"\nper-question rows -> {out}")


if __name__ == "__main__":
    main()
