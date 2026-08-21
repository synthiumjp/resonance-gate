"""Judged A/B: the LoRA extractor vs the prompted 14B, integrity AND accuracy.

The screen (e222) said the adapter earns judge calls: +4.6pt coverage at thr
0.5 with 3.9x fewer emissions. Coverage is a proxy that over-reads judged
recall by ~18pt (e220) and says NOTHING about precision, so the screen cannot
settle it. F1 is a harmonic mean and a 3.9x emission reduction could be given
back entirely on target_accuracy.

Both official judges, called with the same arguments evaluation.py passes:

  integrity  (session's emitted memories, gold point) -> score; 2 = recalled
  accuracy   (session dialogue, session gold, one emitted record)
             -> accuracy_score + is_included_in_golden_memories.
             target_accuracy = mean(0.5 * score) over IN-GOLD records only,
             which is what the harness reports as precision.

Design:
  * both arms scored in ONE run against the SAME gold, so no judge drift;
  * integrity is PAIRED per gold point -> McNemar exact;
  * accuracy is UNPAIRED by construction (the arms emit different records), so
    it is reported as two rates with their record counts;
  * F1 recomputed the harness's way from the two measured halves.

Held-out users only; training users are refused.
"""
import argparse
import collections
import json
import math
import os
import random
import sys

EV = os.path.expanduser("~/rg_private/halumem/official/HaluMem/eval")
DATA = os.path.expanduser("~/rg_private/halumem/HaluMem-Medium.jsonl")
for p in (EV, "/home/jp/rg/experiments/p2"):
    if p not in sys.path:
        sys.path.insert(0, p)
TRAIN_USERS = set(range(10, 20))


def prompted_arm(user, uidx):
    import halumem_run as H
    import propositions as PR
    for cand in (f"~/rg_private/halumem/dev/cache_u{uidx}_v5_14b.jsonl",
                 f"~/rg_private/halumem/cache_u{uidx}_v5.jsonl"):
        c = os.path.expanduser(cand)
        if os.path.exists(c):
            break
    mem, _ = H.ingest_user(user, cache_path=c)
    nodes = list(mem.g.nodes.values()) + list(mem.g.provisional.values())
    owner = PR.owner_name([{"attr": n["attr"], "value": n["value"]} for n in nodes])
    per = collections.defaultdict(list)
    for nd in nodes:
        p = PR.render({"attr": nd["attr"], "value": nd["value"]}, owner=owner)
        if not p:
            continue
        for cid in (nd.get("convs") or {}):
            if str(cid).startswith("s") and str(cid)[1:].isdigit():
                per[int(str(cid)[1:])].append(p)
                break
    return per


def lora_arm(path):
    d = json.load(open(path, encoding="utf-8"))
    return {int(k): [x["content"] for x in v] for k, v in d["sessions"].items()}


def mcnemar(pairs):
    b = sum(1 for x, y in pairs if x and not y)
    c = sum(1 for x, y in pairs if y and not x)
    n = b + c
    if not n:
        return b, c, 1.0
    k = min(b, c)
    return b, c, min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", type=int, required=True)
    ap.add_argument("--lora-artifact", required=True,
                    help="artifact JSON from lora_artifact.py OR "
                         "grammar_artifact.py -- the harness does not care "
                         "which generator produced it")
    ap.add_argument("--label", default="lora")
    ap.add_argument("--limit-integrity", type=int, default=0)
    ap.add_argument("--limit-accuracy", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--reuse", default="",
                    help="verdicts JSON from a previous run; arms found there "
                         "are NOT re-judged. The prompted baseline is fixed, "
                         "so re-scoring it costs ~576 calls for an identical "
                         "answer.")
    ap.add_argument("--save", default="",
                    help="write per-record verdicts here. The first run was "
                         "killed mid-way and its verdicts were lost, forcing "
                         "a full re-judge of an unchanged arm -- ~1100 calls "
                         "for nothing.")
    a = ap.parse_args()
    if a.user in TRAIN_USERS:
        raise SystemExit(f"REFUSING: user {a.user} is a TRAINING user.")

    from eval_tools import (evaluation_for_memory_integrity,
                            evaluation_for_memory_accuracy)
    from concurrent.futures import ProcessPoolExecutor, as_completed

    user = [json.loads(l) for l in open(DATA, encoding="utf-8")][a.user]
    arms = {"prompted": prompted_arm(user, a.user),
            a.label: lora_arm(a.lora_artifact)}
    for k, v in arms.items():
        print(f"{k:<10} {sum(len(x) for x in v.values())} records")

    gold, dial, gstr = {}, {}, {}
    for si, s in enumerate(user["sessions"]):
        gold[si] = [mp for mp in s.get("memory_points", [])
                    if str(mp.get("is_update")) != "True"]
        dial[si] = "\n".join(f"{t.get('role')}: {t.get('content')}"
                             for t in (s.get("dialogue") or []))
        gstr[si] = "\n".join(mp["memory_content"] for mp in gold[si])

    pts = [(si, mp) for si in sorted(gold) for mp in gold[si]]
    if a.limit_integrity:
        pts = pts[:a.limit_integrity]
    print(f"\nintegrity: {len(pts)} gold points x 2 arms = {len(pts)*2} calls")

    def _unkey(k):
        """Saved keys are "<session>|<index>"; rebuild the tuple form."""
        a_, _, b_ = k.partition("|")
        idx = None if b_ in ("None", "") else int(b_)
        return (int(a_), idx)

    prev = {}
    if a.reuse and os.path.exists(a.reuse):
        raw = json.load(open(a.reuse, encoding="utf-8"))
        prev = {arm: {_unkey(k): v for k, v in d.items()}
                for arm, d in raw.items()}
        print(f"  reusing verdicts for: {sorted(prev)}")

    ints = {}
    for arm, per in arms.items():
        if arm in prev and arm != a.label:
            ints[arm] = prev[arm]
            print(f"  [{arm}] reused {len(ints[arm])} verdicts, 0 calls")
            continue
        jobs = [((si, mp.get("index")), "\n".join(per.get(si, [])), mp)
                for si, mp in pts]
        res = {}
        with ProcessPoolExecutor(max_workers=a.workers) as ex:
            fut = {ex.submit(evaluation_for_memory_integrity, blob,
                             mp["memory_content"]): key
                   for key, blob, mp in jobs}
            for i, f in enumerate(as_completed(fut), 1):
                try:
                    res[fut[f]] = int((f.result() or {}).get("score"))
                except Exception:
                    res[fut[f]] = None
                if i % 100 == 0:
                    print(f"  [integrity/{arm}] {i}/{len(jobs)}", flush=True)
        ints[arm] = res

    if a.save:
        json.dump({arm: {"|".join(str(x) for x in k): v for k, v in d.items()}
                   for arm, d in ints.items()},
                  open(a.save, "w", encoding="utf-8"))
        print(f"  saved integrity verdicts to {a.save}")
    keys = [k for k in ints["prompted"]
            if ints["prompted"].get(k) is not None and ints[a.label].get(k) is not None]
    hp = sum(1 for k in keys if ints["prompted"][k] == 2)
    hl = sum(1 for k in keys if ints[a.label][k] == 2)
    print(f"\nINTEGRITY (paired, n={len(keys)})")
    print(f"  prompted recall {hp/len(keys):7.2%}  ({hp}/{len(keys)})")
    print(f"  {a.label:<8} recall {hl/len(keys):7.2%}  ({hl}/{len(keys)})"
          f"   delta {(hl-hp)/len(keys):+.2%}pt")
    b, c, p = mcnemar([(ints["prompted"][k] == 2, ints[a.label][k] == 2)
                       for k in keys])
    print(f"  discordant: prompted-only {b}, {a.label}-only {c}   "
          f"McNemar exact p={p:.4g}")

    print("\nACCURACY (unpaired -- the arms emit different records)")
    prec = {}
    for arm, per in arms.items():
        recs = [(si, r) for si in sorted(per) for r in per[si]]
        if a.limit_accuracy and len(recs) > a.limit_accuracy:
            # SAMPLE, do not take the head. Taking the first N biases toward
            # early sessions, and because arms order their records differently
            # it lands on wildly different in-gold fractions: the spaCy arm's
            # first 200 held 93 in-gold records, the UD arm's held 20. That
            # makes target_accuracy incomparable between arms -- 85% on n=20 is
            # SE~8%, against 93% on n=93 at SE~2.6% -- for a reason that has
            # nothing to do with either extractor.
            rng = random.Random(0)
            recs = rng.sample(recs, a.limit_accuracy)
        k = n = tot = 0
        with ProcessPoolExecutor(max_workers=a.workers) as ex:
            fut = {ex.submit(evaluation_for_memory_accuracy, dial.get(si, ""),
                             gstr.get(si, ""), r): (si, r) for si, r in recs}
            for i, f in enumerate(as_completed(fut), 1):
                tot += 1
                try:
                    d = f.result() or {}
                    if str(d.get("is_included_in_golden_memories")).lower() == "true":
                        n += 1
                        k += 0.5 * int(d.get("accuracy_score"))
                except Exception:
                    pass
                if i % 100 == 0:
                    print(f"  [accuracy/{arm}] {i}/{len(recs)}", flush=True)
        prec[arm] = k / n if n else 0.0
        print(f"  {arm:<9} target_accuracy {prec[arm]:7.2%}  ({k:.1f}/{n} in-gold, "
              f"{tot} emitted)")

    print("\nEXTRACTION F1 (harness definition)")
    for arm, h in (("prompted", hp), (a.label, hl)):
        r = h / max(1, len(keys))
        f1 = 0.0 if prec[arm] + r == 0 else 2 * prec[arm] * r / (prec[arm] + r)
        print(f"  {arm:<9} P {prec[arm]:.4f}  R {r:.4f}  F1 {f1:.4f}")


if __name__ == "__main__":
    main()
