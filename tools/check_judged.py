#!/usr/bin/env python3
"""Refuse a judged row whose judge silently failed.

    python3 tools/check_judged.py <version> [--max-none 0.02]

Review 2026-10-02: `evaluation.py` catches every judge exception and records
the score as None, then aggregates. A judge server that dies mid-run
therefore produces a COMPLETE chain and a RESULT line computed over a store
of Nones, and nothing in the chain could tell. This reads the stat file the
judge just wrote and exits non-zero when any judged stage has more than
`--max-none` of its records unscored. The healthy baseline rows sit at
0.0-0.5% None (qa-rgx4: 3 of 587 integrity, 18 of 3934 accuracy).

Also refuses a stat file OLDER than the results jsonl it was computed from:
`evaluation.py` skips any user with a checkpoint in tmp2/ and re-aggregates
it, so a stale verdict set can be reported as a fresh run.
"""
import argparse
import json
import os
import sys

RESULTS = os.path.expanduser(
    "~/rg_private/halumem/official/HaluMem/eval/results")

# record list -> the field that is None when the judge failed on that record
STAGES = {
    "memory_integrity_records": "memory_integrity_score",
    "memory_accuracy_records": "memory_accuracy_score",
    "memory_update_records": "memory_update_type",
    "question_answering_records": "result_type",
}


def check(version, max_none=0.02, results=RESULTS):
    d = os.path.join(results, f"rgp2-{version}")
    stat = os.path.join(d, "rgp2_eval_stat_result.json")
    src = os.path.join(d, "rgp2_eval_results.jsonl")
    problems = []
    if not os.path.exists(stat):
        return [f"no stat file at {stat}"]
    if os.path.exists(src) and os.path.getmtime(stat) < os.path.getmtime(src):
        problems.append("stat file is OLDER than the results it should score "
                        "-- a stale checkpoint was re-aggregated")
    data = json.load(open(stat))
    for stage, field in STAGES.items():
        rows = data.get(stage) or []
        if not rows:
            continue
        none = sum(1 for r in rows if r.get(field) is None)
        frac = none / len(rows)
        line = f"{stage}: {none}/{len(rows)} unscored ({frac:.1%})"
        print("  " + line)
        if frac > max_none:
            problems.append(line + f" > {max_none:.0%} -- the judge failed")
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("version")
    ap.add_argument("--max-none", type=float, default=0.02)
    a = ap.parse_args(argv)
    problems = check(a.version, a.max_none)
    for p in problems:
        print("FAIL: " + p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
