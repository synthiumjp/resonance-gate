"""p2 oracle instrument (entry 94 formalized): deterministic, judge-free
ceiling metrics for extraction-COVERAGE iteration on the firewalled HaluMem
dev set (users 10-19). No LLM judging anywhere in this file -- pure
token-containment / overlap over an already-ingested Memory, so it runs in
seconds and is directly comparable across extractor prompt versions without
the dev-judge noise entry 94 found (the 1.7b dev judge blesses near-total
abstention as "correct").

Two deterministic numbers, per user and aggregated:
  (a) GOLD-IN-STORE rate over real-gold QUESTIONS: of the questions whose
      gold answer is a REAL value (not a "no info" Memory Boundary answer --
      unknown/not provided/not mentioned/not specified, excluded), for what
      fraction does >=50% of the gold answer's content tokens appear inside
      SOME single stored fact's value? This is the QA ceiling with a
      PERFECT surface -- entry 94's 24.8% number, reproduced here as a
      standing instrument instead of a one-off.
  (b) MEMORY-POINT coverage over non-interference gold memory_points, at
      >=50% and >=30% token-containment thresholds (generalizes
      halumem_run.extraction_proxy, which is the >=50% case, attr+value
      against attr+value) -- the memory_point-level version of the same
      question, independent of QA question phrasing.

Both read the SAME ingested Memory (halumem_run.ingest_user against a
COMPLETE cache -- extraction itself is out of scope here; see dev_set.py
extract / this module has no model-calling code at all).

Usage:
  oracle.py ceiling --users 10-12 [--cache-template PATTERN]
                     [--min-mentions N] [--show-misses N] [--out PATH]

  --cache-template lets the SAME users be scored from a different
  extractor's cache (v4 baseline vs v5 candidate), e.g.:
    oracle.py ceiling --users 10-12 \\
        --cache-template '~/rg_private/halumem/dev/cache_u{i}_17b.jsonl'
    oracle.py ceiling --users 10-12 \\
        --cache-template '~/rg_private/halumem/dev/cache_u{i}_v5_17b.jsonl'
"""

import argparse
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import halumem_run as HR   # ingest_user -- NOT judge_answer (GPU consistency.get_llm())
from wire import _tokens
from dev_set import (_load_users, _parse_users_arg, _cache_path,
                      _cache_complete, DEV_DIR)

# Memory Boundary / no-info gold answers: excluded from the QUESTION ceiling
# the same way entry 94's check excluded them -- these are deliberately
# unanswerable ("Unknown" is the gold), so they cannot register as a
# coverage MISS.
_NO_INFO_RX = re.compile(
    r"\b(unknown|not provided|not mentioned|not specified|no information)\b",
    re.I)


def _stored_value_toks(mem):
    """Content tokens of every stored fact's VALUE only (both tiers) --
    what (a) checks containment against, per entry 94's check."""
    recs = list(mem.g.nodes.values()) + list(mem.g.provisional.values())
    return [_tokens(d["value"]) for d in recs]


def _stored_attr_value_toks(mem):
    """Content tokens of ATTR+VALUE (both tiers) -- what
    halumem_run.extraction_proxy checks memory-point containment against."""
    recs = list(mem.g.nodes.values()) + list(mem.g.provisional.values())
    return [_tokens(d["attr"] + " " + d["value"]) for d in recs]


def gold_in_store(mem, questions, min_frac=0.5):
    """(covered, total, misses) over real-gold questions: a question is
    COVERED if some stored fact VALUE contains >=min_frac of the gold
    answer's content tokens. `misses` is the list of (question, gold) pairs
    that were NOT covered, for --show-misses diagnostics."""
    stored = _stored_value_toks(mem)
    covered, total, misses = 0, 0, []
    for q in questions:
        gold = str(q.get("answer", "")).strip()
        if not gold or _NO_INFO_RX.search(gold):
            continue
        gt = _tokens(gold)
        if not gt:
            continue
        total += 1
        if any(len(gt & st) / len(gt) >= min_frac for st in stored):
            covered += 1
        else:
            misses.append(q)
    return covered, total, misses


def memory_point_coverage(mem, gold_mps, min_frac):
    """(covered, total) over non-interference gold memory_points at
    >=min_frac attr+value token containment -- halumem_run.extraction_proxy
    generalized to an arbitrary threshold (0.5 reproduces it exactly)."""
    stored = _stored_attr_value_toks(mem)
    covered, total = 0, 0
    for mp in gold_mps:
        gt = _tokens(mp.get("memory_content", ""))
        if not gt:
            continue
        total += 1
        if any(len(gt & st) / len(gt) >= min_frac for st in stored):
            covered += 1
    return covered, total


def score_user_ceiling(uidx, user, cache_path, min_mentions=2):
    mem, n_turns = HR.ingest_user(user, cache_path, min_mentions=min_mentions)
    qs = [q for s in user["sessions"] for q in s.get("questions", [])]
    g_cov, g_tot, misses = gold_in_store(mem, qs)
    gold_mps = [mp for s in user["sessions"] for mp in s.get("memory_points", [])
                if mp.get("memory_source") != "interference"]
    mp50_cov, mp50_tot = memory_point_coverage(mem, gold_mps, 0.5)
    mp30_cov, mp30_tot = memory_point_coverage(mem, gold_mps, 0.3)
    return {
        "user": uidx, "n_turns": n_turns,
        "n_asserted": len(mem.g.nodes), "n_provisional": len(mem.g.provisional),
        "gold_in_store_covered": g_cov, "gold_in_store_total": g_tot,
        "gold_in_store_pct": 100 * g_cov / max(g_tot, 1),
        "mp50_covered": mp50_cov, "mp50_total": mp50_tot,
        "mp50_pct": 100 * mp50_cov / max(mp50_tot, 1),
        "mp30_covered": mp30_cov, "mp30_total": mp30_tot,
        "mp30_pct": 100 * mp30_cov / max(mp30_tot, 1),
        "misses": misses,
    }


def cmd_ceiling(args):
    users = _load_users()
    user_indices = _parse_users_arg(args.users)
    rows = []
    for uidx in user_indices:
        user = users[uidx]
        cache_path = _cache_path(uidx, args.cache_template)
        complete, have, total = _cache_complete(user, cache_path)
        if not complete:
            print(f"user {uidx}: cache incomplete ({have}/{total} turns) at "
                  f"{cache_path} -- skipping")
            continue
        row = score_user_ceiling(uidx, user, cache_path, args.min_mentions)
        rows.append(row)
        print(f"user {uidx}: n={row['n_asserted']}+{row['n_provisional']}  "
              f"gold-in-store {row['gold_in_store_pct']:5.1f}% "
              f"({row['gold_in_store_covered']}/{row['gold_in_store_total']})  "
              f"mp>=50% {row['mp50_pct']:5.1f}% ({row['mp50_covered']}/{row['mp50_total']})  "
              f"mp>=30% {row['mp30_pct']:5.1f}% ({row['mp30_covered']}/{row['mp30_total']})")

    if not rows:
        print("\nno dev users had a complete cache -- nothing scored.")
        return

    agg = {}
    for key in ("gold_in_store_covered", "gold_in_store_total",
                "mp50_covered", "mp50_total", "mp30_covered", "mp30_total"):
        agg[key] = sum(r[key] for r in rows)
    agg["gold_in_store_pct"] = 100 * agg["gold_in_store_covered"] / max(agg["gold_in_store_total"], 1)
    agg["mp50_pct"] = 100 * agg["mp50_covered"] / max(agg["mp50_total"], 1)
    agg["mp30_pct"] = 100 * agg["mp30_covered"] / max(agg["mp30_total"], 1)

    print("\n=== aggregate ===")
    print(f"n_users={len(rows)}  "
          f"gold-in-store {agg['gold_in_store_pct']:.1f}% "
          f"({agg['gold_in_store_covered']}/{agg['gold_in_store_total']})  "
          f"mp>=50% {agg['mp50_pct']:.1f}% ({agg['mp50_covered']}/{agg['mp50_total']})  "
          f"mp>=30% {agg['mp30_pct']:.1f}% ({agg['mp30_covered']}/{agg['mp30_total']})")

    if args.show_misses:
        print(f"\n=== up to {args.show_misses} missing golds (question / gold answer) ===")
        shown = 0
        for r in rows:
            for q in r["misses"]:
                if shown >= args.show_misses:
                    break
                print(f"  [u{r['user']}] Q: {q.get('question','')}")
                print(f"        gold: {q.get('answer','')}")
                shown += 1
            if shown >= args.show_misses:
                break

    if args.out:
        out_path = os.path.join(DEV_DIR, args.out)
        with open(out_path, "w") as f:
            json.dump({"per_user": rows, "aggregate": agg,
                       "cache_template": args.cache_template,
                       "min_mentions": args.min_mentions}, f, indent=2)
        print(f"\nsaved {out_path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_ceiling = sub.add_parser("ceiling", help="gold-in-store + memory-point ceiling")
    p_ceiling.add_argument("--users", default=None, help="e.g. '10-12' or '10,11,12'")
    p_ceiling.add_argument("--cache-template", dest="cache_template", default=None,
                           help="path pattern with {i}, e.g. "
                                "'~/rg_private/halumem/dev/cache_u{i}_v5_17b.jsonl' "
                                "(default: dev_set's v4 cache_u{i}_17b.jsonl)")
    p_ceiling.add_argument("--min-mentions", dest="min_mentions", type=int, default=2,
                           help="corroboration threshold for the asserted tier "
                                "(default 2, matches dev_set.score_user)")
    p_ceiling.add_argument("--show-misses", dest="show_misses", type=int, default=0,
                           help="print up to N missing golds (question + gold answer)")
    p_ceiling.add_argument("--out", default=None,
                           help="json filename (written under the dev dir)")

    args = ap.parse_args()
    if args.cmd == "ceiling":
        cmd_ceiling(args)


if __name__ == "__main__":
    main()
