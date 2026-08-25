#!/usr/bin/env python3
"""Entry 250: can RG_SUPERSEDE move the update axis at all?

WHY. The update judge's "Correct Update" criterion says, verbatim:
    "The original memory is effectively replaced or marked as outdated."
RG_SUPERSEDE renders exactly that -- "(updated from: X)" / "(SUPERSEDED by:
Y)" -- and it was OFF in the runs that produced updating 12.6%. So it looks
like the cheapest untested lever on the worst axis.

But before spending a judged cycle, size it. The annotation can only help on
points where it actually FIRES, and it can only help correctly if the old
value it names is the one the gold calls the original. Both are deterministic
and free to check.

This screens three things per gold update point:
  1. does the supersede annotation fire in memories_from_system at all?
  2. when it fires, does the named old value match gold's original_memories?
  3. does turning the flag on change the output string at all?

A low fire rate KILLS the idea outright, at zero GPU cost -- the same way the
context diff killed the verdict-reuse plan. No judge, no model calls.

    python3 tools/supersede_screen.py --user 0
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

MARK = re.compile(r"\((?:updated from|SUPERSEDED by)[:\s]*(.*?)\)\s*$", re.I)
_WORD = re.compile(r"[a-z0-9']+")
_STOP = {"the", "a", "an", "is", "are", "was", "were", "his", "her", "their",
         "to", "of", "and", "in", "for", "on", "with", "as", "that", "this",
         "has", "have", "had", "he", "she", "they", "it", "s", "from"}


def toks(s):
    return {w for w in _WORD.findall((s or "").lower()) if w not in _STOP}


def overlap(a, b):
    A, B = toks(a), toks(b)
    return len(A & B) / len(A) if A else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", type=int, default=0)
    ap.add_argument("--match", type=float, default=0.5,
                    help="token overlap at which the named old value counts "
                         "as matching gold's original_memories")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    os.environ["RG_EXTRACT_V5"] = "1"
    os.environ["RG_RETRIEVE_V3"] = "1"
    os.environ["RG_INGEST_ALL_TURNS"] = "1"
    _EVAL = str(pathlib.Path.home() /
                "rg_private/halumem/official/HaluMem/eval")
    for p in (_P2, _OFFICIAL, _EVAL):
        if p not in sys.path:
            sys.path.insert(0, p)

    import halumem_run as RG      # noqa: E402
    import eval_rgp2 as EV        # noqa: E402

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
        for mp in pts:
            gold_old = " ".join(mp["original_memories"])
            q = mp["memory_content"]
            # currency.mark_current already ran at ingest; RG_SUPERSEDE only
            # gates the RENDERING inside search_memories, so toggling the
            # module attribute is a faithful A/B of the shipped flag.
            EV._SUPERSEDE = False
            off = EV.search_memories(mem, q)
            EV._SUPERSEDE = True
            on = EV.search_memories(mem, q)
            EV._SUPERSEDE = False

            marks = [m.group(1) for s in on for m in [MARK.search(s)] if m]
            best = max((overlap(gold_old, m) for m in marks), default=0.0)
            rows.append({
                "session": k,
                "gold_new": q,
                "gold_old": gold_old,
                "changed": off != on,
                "fired": bool(marks),
                "n_marks": len(marks),
                "best_old_match": round(best, 3),
                "marks": marks[:3],
                "empty_retrieval": not on,
            })
        print(f"  session {k}: {len(rows)} update points", file=sys.stderr)

    n = len(rows)
    if not n:
        sys.exit("no update points")
    fired = sum(r["fired"] for r in rows)
    changed = sum(r["changed"] for r in rows)
    matched = sum(r["best_old_match"] >= args.match for r in rows)
    empty = sum(r["empty_retrieval"] for r in rows)

    print(f"\n=== RG_SUPERSEDE screen: user {args.user}, {n} gold update "
          f"points ===\n")
    print(f"  output changes when flag flipped : {changed:4d}/{n} "
          f"({100*changed/n:.1f}%)")
    print(f"  supersede annotation FIRES       : {fired:4d}/{n} "
          f"({100*fired/n:.1f}%)  <- ceiling on any gain")
    print(f"  named old value matches gold     : {matched:4d}/{n} "
          f"({100*matched/n:.1f}%)  <- realistic ceiling")
    print(f"  empty retrieval (escapes axis)   : {empty:4d}/{n} "
          f"({100*empty/n:.1f}%)")
    if fired:
        print("\n  sample fired annotations:")
        for r in [r for r in rows if r["fired"]][:5]:
            print(f"    gold old : {r['gold_old'][:90]}")
            print(f"    we named : {r['marks'][0][:90]}  "
                  f"(overlap {r['best_old_match']})")
    out = args.out or f"/tmp/supersede_screen_u{args.user}.jsonl"
    with open(out, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    print(f"\nper-point rows -> {out}")


if __name__ == "__main__":
    main()
