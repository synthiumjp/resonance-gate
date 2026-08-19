"""p2 ANCHOR LAB (mission: entity+attribute anchoring, dev users 10-12, 14B
v5.1 caches): deterministic proxy comparison of THREE plain-surface answer
policies, no model/judge call anywhere:

  BLOB        halumem_run._answer_plain, shipped default (RG_SINGLE_FACT
              unset) -- ranked candidates joined up to RG_COMPOSE_BUDGET.
  SINGLE-FACT halumem_run._answer_plain with RG_SINGLE_FACT=1 -- same
              selection/ranking as BLOB, but returns only the single
              highest-ranked candidate (entry 98's test config; this is
              what the "31% hallucination even one fact at a time" mission
              premise measured against the REAL judge).
  ANCHORED    halumem_run._answer_anchored (FIX K, RG_ANCHORED) -- question
              routed to its asked ATTRIBUTE TYPE(S) first, candidates
              restricted to that attribute, THEN ranked by value-token
              overlap; abstains when no attribute of the asked type is
              asked about or none is stored.

THE DIAGNOSIS this lab exists to test (see halumem_run.py's FIX K comment
block): BLOB/SINGLE-FACT both rank over the WHOLE store by value-token
overlap, so a "job title" question can be answered by any narrative fact
that happens to share a word with the question -- a real, receipted fact
that is simply WRONG FOR THE QUESTION (mis-selection, not fabrication).
ANCHORED's hypothesis is that restricting candidates to the asked
ATTRIBUTE TYPE before ranking fixes the mis-selection at the cost of
answering fewer questions (abstaining whenever the question's attribute
type isn't recognized or isn't stored).

METRICS (all local, deterministic, token-overlap proxies -- NOT the
official judge; see mission notes for why these are directionally
trustworthy but not to be quoted as final numbers):
  PROXY-CORRECT  -- % of real-gold questions whose (non-abstain) answer
                     contains >=50% of gold's content tokens. Same
                     definition as gate_lab/surface_lab's DELIVERED, over
                     n_real. Want UP.
  WRONG-ASSERT   -- % of ALL composed (non-"Unknown.") answers -- both
                     real-gold and Unknown-gold questions -- that share
                     <20% tokens with gold. This is the hallucination
                     proxy: a composed answer that barely overlaps gold at
                     all (or is composed on a question whose gold IS
                     "Unknown", so any composed answer inherently shares
                     ~0% with gold's "not provided" wording) is exactly
                     the mis-selection failure mode the mission is
                     diagnosing. Want DOWN HARD.
  ABSTAIN-RATE   -- % of ALL questions answered "Unknown."
  ABSTAIN-ON-UNKNOWN-GOLD -- % of Unknown-gold questions correctly
                     abstained (the trust lever: abstaining IS correct
                     there, not a miss).

Usage: anchor_lab.py [--users 10-12] [--min-mentions 2] [--by-type]
"""

import argparse
import os
import sys
from collections import defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import halumem_run as HR
from wire import _tokens
from surface_lab import HALUMEM_PATH, CACHE_TEMPLATE, load_dev_users, _is_unknown_gold


def _token_overlap_frac(gold, answer):
    """Fraction of GOLD's content tokens present in `answer` -- the same
    >=50% containment test as DELIVERED, but returned as a raw fraction so
    WRONG-ASSERT can threshold it at <20% instead."""
    gt = _tokens(gold)
    if not gt:
        return 1.0   # no content tokens in gold (rare) -- can't be "wrong"
    at = _tokens(answer)
    return len(gt & at) / len(gt)


def score_policy(mems, name, env_key, env_val):
    """Runs halumem_run.answer_question(surface='plain') over every user's
    questions with `env_key` set to `env_val` (or unset if env_val is
    None) for the duration of the run, and computes the proxy table."""
    old = os.environ.get(env_key) if env_key else None
    try:
        if env_key:
            if env_val is None:
                os.environ.pop(env_key, None)
            else:
                os.environ[env_key] = env_val
        n_total = n_real = n_unk = 0
        n_delivered = n_unk_composed = n_composed = n_wrong = 0
        n_abstain_on_unk = 0
        by_type = defaultdict(lambda: defaultdict(int))
        for uidx, (mem, qs) in mems.items():
            for q in qs:
                gold = str(q.get("answer", "")).strip()
                qtype = q.get("question_type", "?")
                ans = HR.answer_question(mem, q["question"], surface="plain")
                n_total += 1
                by_type[qtype]["n"] += 1
                composed = ans != "Unknown."
                if composed:
                    n_composed += 1
                    by_type[qtype]["composed"] += 1
                    if _token_overlap_frac(gold, ans) < 0.20:
                        n_wrong += 1
                        by_type[qtype]["wrong"] += 1
                if _is_unknown_gold(gold):
                    n_unk += 1
                    if composed:
                        n_unk_composed += 1
                    else:
                        n_abstain_on_unk += 1
                elif gold:
                    n_real += 1
                    if composed and _token_overlap_frac(gold, ans) >= 0.50:
                        n_delivered += 1
                        by_type[qtype]["delivered"] += 1
        return {
            "name": name,
            "n_total": n_total,
            "proxy_correct": 100 * n_delivered / max(n_real, 1),
            "n_delivered": n_delivered, "n_real": n_real,
            "wrong_assert": 100 * n_wrong / max(n_composed, 1),
            "n_wrong": n_wrong, "n_composed": n_composed,
            "abstain_rate": 100 * (n_total - n_composed) / max(n_total, 1),
            "abstain_on_unknown": 100 * n_abstain_on_unk / max(n_unk, 1),
            "n_abstain_on_unk": n_abstain_on_unk, "n_unk": n_unk,
            "by_type": by_type,
        }
    finally:
        if env_key:
            if old is None:
                os.environ.pop(env_key, None)
            else:
                os.environ[env_key] = old


POLICIES = [
    ("BLOB (shipped, joined up to budget)", "RG_SINGLE_FACT", None),
    ("SINGLE-FACT (shipped selection, 1 value)", "RG_SINGLE_FACT", "1"),
    ("ANCHORED (FIX K, RG_ANCHORED)", "RG_ANCHORED", "1"),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--users", default="10-12")
    ap.add_argument("--min-mentions", dest="min_mentions", type=int, default=2)
    ap.add_argument("--cache-template", dest="cache_template", default=CACHE_TEMPLATE)
    ap.add_argument("--by-type", action="store_true")
    args = ap.parse_args()

    a, b = args.users.split("-") if "-" in args.users else (args.users, args.users)
    user_indices = list(range(int(a), int(b) + 1))

    print(f"loading users {user_indices} from v5.1 14B caches ...")
    mems = load_dev_users(user_indices, args.min_mentions, args.cache_template)
    total_q = sum(len(qs) for _, qs in mems.values())
    print(f"{len(mems)} users, {total_q} questions total\n")

    assert os.environ.get("RG_ANCHORED") is None, "RG_ANCHORED must not leak into this process's ambient env"
    assert os.environ.get("RG_SINGLE_FACT") is None, "RG_SINGLE_FACT must not leak into this process's ambient env"

    hdr = (f"{'policy':42s} {'PROXY-COR%':>10s} {'(n)':>9s} {'WRONG-A%':>9s} "
           f"{'(n)':>9s} {'ABSTAIN%':>9s} {'ABST-UNK%':>10s} {'(n)':>7s}")
    print(hdr)
    print("-" * len(hdr))
    rows = []
    for name, env_key, env_val in POLICIES:
        row = score_policy(mems, name, env_key, env_val)
        rows.append(row)
        print(f"{name:42s} {row['proxy_correct']:10.1f} "
              f"{row['n_delivered']:>3d}/{row['n_real']:<5d} "
              f"{row['wrong_assert']:9.1f} "
              f"{row['n_wrong']:>3d}/{row['n_composed']:<5d} "
              f"{row['abstain_rate']:9.1f} {row['abstain_on_unknown']:10.1f} "
              f"{row['n_abstain_on_unk']:>3d}/{row['n_unk']:<3d}")

    print(f"\nTARGET: WRONG-ASSERT < 40.0 with PROXY-CORRECT >= 20.0")

    if args.by_type:
        print("\nby question_type (composed / delivered / wrong-assert, per policy):")
        for row in rows:
            print(f"  {row['name']}")
            for t, d in sorted(row["by_type"].items()):
                print(f"    {t:32s} n={d['n']:3d}  composed {d.get('composed',0):3d}  "
                      f"delivered {d.get('delivered',0):3d}  wrong {d.get('wrong',0):3d}")


if __name__ == "__main__":
    main()
