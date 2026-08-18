"""Judged A/B of W1 (write-time supersession) on the UPDATE axis only.

Our updating accuracy is 2.9% -- worst of the eight systems with published
HaluMem numbers (e211) -- and W1 exists to move it. This measures whether it
does, with the OFFICIAL judge, for 270 calls instead of the 3,644 a full
two-arm pass costs.

Why that shortcut is legitimate rather than a corner cut:

  * the update metric's only input is `memories_from_system`, which the
    harness fills from search_memories() -- PURE RETRIEVAL, no model call. So
    both arms' inputs are generated offline and exactly, not approximated.
  * the judge is the harness's own evaluation_for_update_memory, called with
    the same three arguments evaluation.py passes it, in the same order.
  * both arms are scored in ONE run against the SAME gold update points, so
    the comparison is paired and no judge-version drift can enter.

ONE VARIABLE. Both arms run today's code -- slot hygiene, qualifier handling,
write-time marking all present in both. The only difference is whether
search_memories REPORTS the supersession it already knows about.

Nothing here writes to results/, so it cannot contaminate a real run.
"""
import argparse
import collections
import json
import math
import os
import sys

EV = os.path.expanduser("~/rg_private/halumem/official/HaluMem/eval")
DATA = os.path.expanduser("~/rg_private/halumem/HaluMem-Medium.jsonl")
CACHE = os.path.expanduser("~/rg_private/halumem/dev/cache_u10_v5_14b.jsonl")
for p in (EV, "/home/jp/rg/experiments/p2"):
    if p not in sys.path:
        sys.path.insert(0, p)


def build(user, flag):
    import halumem_run as H
    import eval_rgp2 as E
    E._SUPERSEDE = flag
    mem, _ = H.ingest_user(user, cache_path=CACHE)
    rows = []
    for si, sess in enumerate(user["sessions"]):
        for mp in sess.get("memory_points", []):
            if str(mp.get("is_update")) != "True":
                continue
            rows.append({
                "key": (si, mp.get("index"), mp.get("memory_content")),
                "memory_content": mp.get("memory_content", ""),
                "original_memories": mp.get("original_memories", []) or [],
                "memories_from_system": E.search_memories(
                    mem, mp.get("memory_content", "")),
            })
    return rows


def judge(rows, label):
    from eval_tools import evaluation_for_update_memory
    from concurrent.futures import ProcessPoolExecutor, as_completed
    out = {}
    with ProcessPoolExecutor(max_workers=4) as ex:
        fut = {ex.submit(evaluation_for_update_memory,
                         "\n".join(r["memories_from_system"]),
                         r["memory_content"],
                         "\n".join(r["original_memories"])): r for r in rows}
        for i, f in enumerate(as_completed(fut), 1):
            r = fut[f]
            try:
                res = f.result()
            except Exception as e:
                res = {"result_type": None, "error": str(e)}
            # evaluation.py:170 reads "evaluation_result", NOT "result_type" --
            # the latter is what the QA judge uses, and reading it here made
            # every record score None while the run still exited 0.
            out[r["key"]] = (res or {}).get("evaluation_result")
            if i % 25 == 0:
                print(f"  [{label}] {i}/{len(rows)}", flush=True)
    return out


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
    ap.add_argument("--user", type=int, default=10)
    a = ap.parse_args()
    user = [json.loads(l) for l in open(DATA, encoding="utf-8")][a.user]

    off = build(user, False)
    on = build(user, True)
    print(f"{len(off)} gold update points for user {a.user}")
    changed = sum(1 for x, y in zip(off, on)
                  if x["memories_from_system"] != y["memories_from_system"])
    print(f"readout differs on {changed} of them "
          f"({changed/max(1,len(off)):.0%}) -- the rest cannot move\n")

    r_off = judge(off, "off")
    r_on = judge(on, "on")

    keys = [r["key"] for r in off if r["key"] in r_off and r["key"] in r_on]
    print(f"\npaired n={len(keys)}")
    for lab, res in (("SUPERSEDE off", r_off), ("SUPERSEDE on ", r_on)):
        c = collections.Counter(res[k] for k in keys)
        tot = len(keys)
        parts = "  ".join(f"{k or 'None'} {v/tot:.1%}" for k, v in c.most_common())
        print(f"  {lab}: {parts}")

    VALID = ("Correct", "Hallucination", "Omission", "Other")
    bad = sum(1 for k in keys if r_off[k] not in VALID or r_on[k] not in VALID)
    if bad:
        print(f"  WARNING: {bad}/{len(keys)} records scored outside "
              f"{VALID} -- the harness treats those as invalid")
    for lab in ("Correct", "Hallucination", "Omission"):
        pairs = [(r_off[k] == lab, r_on[k] == lab) for k in keys]
        b, c, p = mcnemar(pairs)
        print(f"  {lab:<14} off-only {b:3d}  on-only {c:3d}   McNemar exact p={p:.4g}")
    # restricted to the readouts that actually changed -- the rest are ties by
    # construction and only dilute the test
    ch = {r["key"] for r, y in zip(off, on)
          if r["memories_from_system"] != y["memories_from_system"]}
    sub = [k for k in keys if k in ch]
    if sub:
        pairs = [(r_off[k] == "Correct", r_on[k] == "Correct") for k in sub]
        b, c, p = mcnemar(pairs)
        print(f"\n  restricted to the {len(sub)} CHANGED readouts:")
        print(f"    Correct  off-only {b}, on-only {c}   McNemar exact p={p:.4g}")
    print("  (only the {} readouts that actually differ can contribute)".format(changed))


if __name__ == "__main__":
    main()
