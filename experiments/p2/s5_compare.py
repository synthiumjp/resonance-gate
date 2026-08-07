"""Compare the two S5 arms on the OFFICIAL judge's own records.

Reads results/rgp2-s5-{base,all}-j/tmp2/*.json -- the per-chunk checkpoints
evaluation.py writes -- and reports every axis with its appropriate test.

Which test goes with which axis, and why it matters here:

  INTEGRITY  paired. Both arms are judged on the SAME gold memory points (same
             user, same sessions, same chunking), so each gold point is one
             matched pair and McNemar is exact. This is the axis entry 194's
             +14.01pt claim lives on, and pairing is what makes a small n
             informative -- entry 194's own null scare came from comparing
             across cohorts instead of within one.

  ACCURACY   UNPAIRED, unavoidably. The arms emit different memories, so there
             is nothing to pair: all-turns emits 1590 strings against base's
             1014, and the question is what fraction of each set is judged
             sound. Reported as two rates with Wilson intervals. A difference
             here is weaker evidence than the same difference on integrity.

  F1         the harness's own combination: precision = target_accuracy(all),
             recall = integrity recall(all). Recomputed here from pooled
             records so it matches what evaluation.py would write, without
             needing the full aggregate to have run.

  QA         paired on the question. Secondary -- the store changed, so QA
             moving is expected; it is reported to catch a large regression,
             not as the headline.

Absolute numbers here are judged, so unlike entry 202's proxy they can be
quoted. What they cannot do is generalise beyond user 10.
"""
import glob
import json
import math
import os
from collections import defaultdict

EV = os.path.expanduser("~/rg_private/halumem/official/HaluMem/eval")


def load(arm):
    recs = defaultdict(list)
    files = sorted(glob.glob(f"{EV}/results/rgp2-s5-{arm}-j/tmp2/*.json"))
    for f in files:
        d = json.load(open(f, encoding="utf-8"))
        for k, v in d.items():
            if isinstance(v, list):
                recs[k].extend(v)
    return recs, len(files)


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def mcnemar(pairs):
    """pairs: list of (base_ok, all_ok). Exact binomial two-sided on the
    discordant cells -- exact rather than chi-square because the discordant
    count can be small at this n."""
    b = sum(1 for x, y in pairs if x and not y)   # base only
    c = sum(1 for x, y in pairs if y and not x)   # all only
    n = b + c
    if n == 0:
        return b, c, 1.0
    k = min(b, c)
    p = 2 * sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return b, c, min(1.0, p)


def integrity(recs):
    """(correct, total) over non-interference gold points, keyed for pairing."""
    out = {}
    for r in recs["memory_integrity_records"]:
        if r.get("memory_source") == "interference":
            continue
        key = (r["uuid"], r["ssession_id"], r["memory_content"])
        out[key] = (r.get("memory_integrity_score") == 2)
    return out


def accuracy(recs):
    tgt_k = tgt_n = 0
    for r in recs["memory_accuracy_records"]:
        if r.get("is_included_in_golden_memories") in ("true", "True"):
            tgt_n += 1
            s = r.get("memory_accuracy_score")
            if s is not None:
                tgt_k += 0.5 * s
    return tgt_k, tgt_n, len(recs["memory_accuracy_records"])


def qa(recs):
    out = {}
    for r in recs["question_answering_records"]:
        key = (r["uuid"], r["ssession_id"], r["question"])
        out[key] = r.get("result_type")
    return out


def f1(p, r):
    return 0.0 if p + r == 0 else 2 * p * r / (p + r)


def main():
    arms = {}
    for arm in ("base", "all"):
        recs, nf = load(arm)
        arms[arm] = recs
        print(f"{arm}: {nf} chunks, "
              f"{len(recs['memory_integrity_records'])} integrity, "
              f"{len(recs['memory_accuracy_records'])} accuracy, "
              f"{len(recs['question_answering_records'])} qa")
    print()

    ib, ia = integrity(arms["base"]), integrity(arms["all"])
    shared = sorted(set(ib) & set(ia))
    print(f"INTEGRITY (paired, n={len(shared)} gold points; "
          f"base-only keys {len(set(ib)-set(ia))}, all-only {len(set(ia)-set(ib))})")
    kb = sum(ib[k] for k in shared)
    ka = sum(ia[k] for k in shared)
    for nm, k in (("base", kb), ("all ", ka)):
        lo, hi = wilson(k, len(shared))
        print(f"  {nm} recall {k/len(shared):7.2%}  [{lo:.2%}, {hi:.2%}]  ({k}/{len(shared)})")
    b, c, p = mcnemar([(ib[k], ia[k]) for k in shared])
    print(f"  delta {(ka-kb)/len(shared):+.2%}pt   discordant: base-only {b}, "
          f"all-only {c}   McNemar exact p={p:.4g}")
    print()

    print("ACCURACY (unpaired -- the arms emit different memories)")
    prec = {}
    for arm in ("base", "all"):
        k, n, tot = accuracy(arms[arm])
        prec[arm] = k / n if n else 0.0
        lo, hi = wilson(round(k), n)
        print(f"  {arm:4s} target_accuracy {prec[arm]:7.2%}  [{lo:.2%}, {hi:.2%}]  "
              f"({k:.1f}/{n} target, {tot} emitted)")
    print()

    print("EXTRACTION F1 (harness definition: precision=target_accuracy, recall=integrity)")
    for arm, ivals in (("base", ib), ("all", ia)):
        r = sum(ivals.values()) / max(1, len(ivals))
        print(f"  {arm:4s} P {prec[arm]:.4f}  R {r:.4f}  F1 {f1(prec[arm], r):.4f}")
    print()

    qb, qa_ = qa(arms["base"]), qa(arms["all"])
    sq = sorted(set(qb) & set(qa_))
    if sq:
        print(f"QA (paired, n={len(sq)})")
        for nm, d in (("base", qb), ("all ", qa_)):
            cnt = defaultdict(int)
            for k in sq:
                cnt[d[k]] += 1
            tot = len(sq)
            print(f"  {nm} correct {cnt['Correct']/tot:6.2%}  "
                  f"hallucination {cnt['Hallucination']/tot:6.2%}  "
                  f"omission {cnt['Omission']/tot:6.2%}")
        pairs = [(qb[k] == "Correct", qa_[k] == "Correct") for k in sq]
        b, c, p = mcnemar(pairs)
        print(f"  discordant: base-only {b}, all-only {c}   McNemar exact p={p:.4g}")


if __name__ == "__main__":
    main()
