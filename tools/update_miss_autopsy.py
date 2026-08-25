#!/usr/bin/env python3
"""Entry 252: WHY do 69% of update-gold points never reach the store?

e252's funnel showed the update axis is an extraction problem: 98 of u0's 142
gold update points die at stage (i), the new content simply is not stored.
This localises each of those deaths against the actual dialogue and the actual
extraction cache, so the next parser round attacks a measured population
instead of whatever was most recently annoying.

For each dying point:
  1. find the dialogue turn that best carries the gold's new content
  2. look up what rgx ACTUALLY extracted from that turn (the cache is keyed by
     sha1 of the turn text, so this is the real emission, not a re-run)
  3. classify the death:

     NOT_IN_DIALOGUE  no turn carries the content -- gold is inferred or
                      spread across turns; unreachable by any single-clause
                      walker, and the honest ceiling on this axis.
     TURN_NOT_READ    the carrying turn is an assistant turn and the run did
                      not ingest assistant turns.
     EMITTED_NOTHING  the turn was read and produced no records at all --
                      a parser coverage hole, the highest-value class.
     EMITTED_OTHER    the turn produced records, none covering the gold --
                      the clause carrying the change was missed while its
                      neighbours were emitted.
     PARTIAL          a record partly covers the gold (a FORM problem: we
                      said it, differently).

*** Containment is a descriptive localiser, not an accuracy metric. ***

    python3 tools/update_miss_autopsy.py --user 0 --examples 12
"""
import argparse
import collections
import hashlib
import json
import os
import pathlib
import re
import sys

_P2 = "/home/jp/rg/experiments/p2"
_OFFICIAL = os.path.join(_P2, "halumem_official")
_EVAL = str(pathlib.Path.home() / "rg_private/halumem/official/HaluMem/eval")
DATA = pathlib.Path.home() / "rg_private" / "halumem" / "HaluMem-Medium.jsonl"

_WORD = re.compile(r"[a-z0-9']+")
_STOP = {"the", "a", "an", "is", "are", "was", "were", "his", "her", "their",
         "to", "of", "and", "in", "for", "on", "with", "as", "that", "this",
         "has", "have", "had", "he", "she", "they", "it", "s", "from", "by",
         "at", "be", "been", "or", "but", "not", "its", "also", "which"}


def toks(s):
    return {w for w in _WORD.findall((s or "").lower()) if w not in _STOP}


def contained(gold, cand):
    G = toks(gold)
    return len(G & toks(cand)) / len(G) if G else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", type=int, default=0)
    ap.add_argument("--cover", type=float, default=0.6)
    ap.add_argument("--examples", type=int, default=10)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    os.environ["RG_EXTRACT_V5"] = "1"
    os.environ["RG_RETRIEVE_V3"] = "1"
    os.environ["RG_INGEST_ALL_TURNS"] = "1"
    for p in (_P2, _OFFICIAL, _EVAL):
        if p not in sys.path:
            sys.path.insert(0, p)
    import halumem_run as RG      # noqa: E402

    cache_path = (pathlib.Path.home() /
                  f"rg_private/halumem/qa_rgx/cache_u{args.user}_v5.jsonl")
    cache = {}
    for line in cache_path.open():
        try:
            d = json.loads(line)
            cache[d["h"]] = d["f"]
        except Exception:
            pass

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
                                cache_path.as_posix(), min_mentions=2)
        nodes = list(mem.g.nodes.values()) + list(mem.g.provisional.values())
        store = [nd.get("text") or f"{nd['attr']}: {nd['value']}" for nd in nodes]
        # only turns from THIS session can carry a change new as of it
        turns = session.get("dialogue", [])

        for mp in pts:
            gold = mp["memory_content"]
            if max((contained(gold, s) for s in store), default=0.0) >= args.cover:
                continue                       # survived stage (i)

            best_t, best_c = None, 0.0
            for t in turns:
                c = contained(gold, t.get("content", ""))
                if c > best_c:
                    best_t, best_c = t, c

            recs, cov = [], 0.0
            if best_t is not None:
                h = hashlib.sha1(best_t["content"].encode()).hexdigest()
                recs = cache.get(h) or []
                cov = max((contained(gold, r.get("text") or "")
                           for r in recs), default=0.0)

            if best_t is None or best_c < args.cover:
                cls = "NOT_IN_DIALOGUE"
            elif not recs:
                cls = ("TURN_NOT_READ" if best_t.get("role") == "assistant"
                       and h not in cache else "EMITTED_NOTHING")
            elif cov >= args.cover:
                cls = "STORED_BUT_LOST"        # emitted yet absent from store
            elif cov >= 0.35:
                cls = "PARTIAL"
            else:
                cls = "EMITTED_OTHER"

            rows.append({
                "session": k, "class": cls, "gold": gold,
                "turn_cover": round(best_c, 3),
                "turn_role": best_t.get("role") if best_t else None,
                "turn": (best_t.get("content") if best_t else "")[:400],
                "n_records": len(recs),
                "best_record_cover": round(cov, 3),
                "best_record": max((r.get("text") or "" for r in recs),
                                   key=lambda t: contained(gold, t),
                                   default=""),
            })
        print(f"  session {k}: {len(rows)} deaths localised", file=sys.stderr)

    n = len(rows)
    if not n:
        sys.exit("no stage-(i) deaths found")
    c = collections.Counter(r["class"] for r in rows)
    print(f"\n=== stage-(i) autopsy: user {args.user}, {n} deaths ===\n")
    for cls, v in c.most_common():
        print(f"  {cls:<18s}{v:4d}  ({100*v/n:5.1f}%)")
    roles = collections.Counter(r["turn_role"] for r in rows
                                if r["class"] != "NOT_IN_DIALOGUE")
    print(f"\n  carrying-turn role (reachable only): {dict(roles)}")

    out = args.out or f"/tmp/update_miss_u{args.user}.jsonl"
    with open(out, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")

    for cls in ("EMITTED_NOTHING", "EMITTED_OTHER", "PARTIAL"):
        ex = [r for r in rows if r["class"] == cls][:args.examples // 3 or 2]
        if not ex:
            continue
        print(f"\n--- {cls} ---")
        for r in ex:
            print(f"  GOLD  : {r['gold'][:150]}")
            print(f"  TURN  : ({r['turn_role']}) {r['turn'][:150]}")
            print(f"  BEST  : {r['best_record'][:150]}  "
                  f"[cov {r['best_record_cover']}, {r['n_records']} recs]")
            print()
    print(f"per-point rows -> {out}")


if __name__ == "__main__":
    main()
