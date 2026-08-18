"""Rank what the judge scored WORST, and cluster it into bug classes.

We have run the official judge many times and consumed exactly one number
from each run: the pooled mean. Meanwhile every run wrote a per-record score
for every memory we emitted, and those scores were telling us things we never
read. The 7% of user 10's store that was malformed English scored 0.278
against 0.652 for everything else -- a two-and-a-half-fold penalty, visible in
a file we already had, for months.

The offline proxies could not have caught it: they compare token SETS, so they
are near-invariant to whether the words form a sentence. But the judge is an
LLM reading prose, and it noticed. Nobody asked it.

So this asks. Two views, and the second is the point:

  worst records   the lowest-scoring memories, verbatim. What a bug report
                  would quote.
  bug classes     recurring surface patterns among the low scorers, scored
                  against the SAME pattern's rate among high scorers. A
                  pattern that appears in 40% of bad records and 38% of good
                  ones is a description of our writing style, not a defect --
                  only the lift makes it a bug.

The lift is the whole design. Ranking by raw frequency surfaces "michelle"
and "plans", which appear everywhere; ranking by lift surfaces "plans to
<gerund>", which appears only where the judge is unhappy.

Run this on any judged results dir before deciding what to work on next.
No model calls -- it reads scores that were already paid for.
"""
import argparse
import collections
import glob
import json
import os
import re

RESULTS = os.path.expanduser(
    "~/rg_private/halumem/official/HaluMem/eval/results")
LOW, HIGH = 0.5, 1.5      # accuracy scores are 0 / 1 / 2


def load(version, in_gold_only=True):
    """THE CONFOUND, and it nearly cost me a wrong conclusion.

    memory_accuracy_score is almost a restatement of gold membership: on
    s5-base the in-gold records mean 1.330 and the out-of-gold records mean
    0.022, and NO in-gold record scores 0. So ranking all records by score
    ranks them by "is this in HaluMem's answer key", and the resulting
    "bug classes" are a list of things we extract that the benchmark did not
    enumerate -- a coverage difference, not a defect.

    Reading it unconditioned told me malformed records scored 0.278 against
    0.652, i.e. that the judge had been flagging our grammar bug all along.
    Conditioned on gold membership the real gap is 1.000 vs 1.345 on n=20 --
    a modest penalty on a handful of records, not a signal anyone missed.

    So: in-gold only by default. Those are records the benchmark expected and
    scored, where a low score really does mean we got it wrong."""
    out = []
    for f in glob.glob(f"{RESULTS}/rgp2-{version}/tmp2/*.json"):
        for r in json.load(open(f, encoding="utf-8")).get(
                "memory_accuracy_records", []):
            if r.get("memory_accuracy_score") is None:
                continue
            ing = str(r.get("is_included_in_golden_memories")).lower() == "true"
            if in_gold_only and not ing:
                continue
            out.append((float(r["memory_accuracy_score"]),
                        str(r.get("memory_content", ""))))
    return out


def shapes(text):
    """Surface patterns a bug would show up as: adjacent word-shape bigrams,
    with content words abstracted away so "plans to joining" and "plans to
    exploring" collapse to one pattern instead of two."""
    w = re.findall(r"[a-z']+", text.lower())
    def cls(x):
        if x.endswith("ing"):
            return "<GERUND>"
        if x in ("to", "by", "as", "is", "of", "in", "at", "for", "with",
                 "plans", "aims", "motivated", "values", "believes", "works",
                 "lives", "prefers", "enjoys", "has", "does", "feels"):
            return x
        return "<W>"
    c = [cls(x) for x in w]
    out = set()
    for i in range(len(c) - 2):
        tri = " ".join(c[i:i + 3])
        if tri.count("<W>") < 3:
            out.add(tri)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="s5-base-j")
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--all-records", action="store_true",
                    help="include records not in gold -- this makes the "
                         "ranking a gold-coverage diff, not a defect list")
    a = ap.parse_args()

    recs = load(a.version, in_gold_only=not a.all_records)
    if not recs:
        print(f"no scored accuracy records in rgp2-{a.version}")
        return
    bad = [t for s, t in recs if s <= LOW]
    good = [t for s, t in recs if s >= HIGH]
    scope = "ALL records (gold-coverage diff, NOT a defect list)" if a.all_records \
        else "in-gold records only"
    print(f"scope: {scope}")
    print(f"rgp2-{a.version}: {len(recs)} scored records, "
          f"{len(bad)} scored <={LOW}, {len(good)} scored >={HIGH}, "
          f"mean {sum(s for s, _ in recs)/len(recs):.3f}\n")

    fb, fg = collections.Counter(), collections.Counter()
    for t in bad:
        fb.update(shapes(t))
    for t in good:
        fg.update(shapes(t))

    print("BUG CLASSES -- surface patterns over-represented among low scorers")
    print(f"  {'pattern':<34}{'in bad':>9}{'in good':>9}{'lift':>8}{'cost':>8}")
    rows = []
    for p, nb in fb.items():
        if nb < max(5, 0.02 * len(bad)):
            continue
        rb, rg = nb / len(bad), fg[p] / max(1, len(good))
        lift = rb / rg if rg else float("inf")
        if lift > 1.5:
            # cost = records we would plausibly recover by fixing this class
            rows.append((nb * (1 - 1 / lift) if lift != float("inf") else nb,
                         p, nb, fg[p], lift))
    for cost, p, nb, ng, lift in sorted(rows, reverse=True)[:a.top]:
        lf = "inf" if lift == float("inf") else f"{lift:.1f}x"
        print(f"  {p:<34}{nb:>9}{ng:>9}{lf:>8}{cost:>8.0f}")
    if not rows:
        print("  (none clear the lift bar -- no dominant surface defect)")

    print(f"\nWORST RECORDS, verbatim")
    for s, t in sorted(recs, key=lambda x: x[0])[:a.top]:
        print(f"  [{s:.0f}] {t[:96]}")

    print("\n  'cost' estimates records recoverable if that class scored like")
    print("  the rest. Fix by cost, not by lift -- a 10x lift on 6 records is")
    print("  a curiosity; a 2x lift on 200 is the afternoon's work.")


if __name__ == "__main__":
    main()
