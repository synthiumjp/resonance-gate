"""Judged A/B of COMPOSITION on the integrity (recall) axis.

Extraction F1 is the harmonic mean of precision -- healthy at 0.665 -- and
integrity recall, which is 0.29 and is the whole gap. F1 0.50 needs recall
0.40; Mem0 parity needs 0.50 (e216).

e206/e215 localised the lever: the judge credits RECORDS, and gold bundles two
or three propositions into a sentence where we emit the parts separately. Late
misses have 50.0% coverage by the UNION of a session's emissions and 15.1% by
any single record. Composing gold-shaped compound records is therefore the
candidate, and merge_probe puts the offline lever at +5.6pt over a matched
null.

This prices it with the OFFICIAL judge, which is the only thing that settles
it -- e213/e214 spent four A/Bs on architecturally-correct changes that the
proxy liked and the judge did not.

Design notes that make the comparison honest:

  * both arms are built from the SAME store in the SAME process, so the only
    difference is what is emitted;
  * compounds are emitted ALONGSIDE atoms, never instead -- the store keeps
    its addressable units, and the arms differ by addition only, which makes
    the pairing exact;
  * every gold point is judged in BOTH arms in one run, so no judge drift can
    enter, and McNemar is exact on the discordant cells;
  * RECORD COUNT is reported. It is the denominator of target_accuracy, so
    recall bought by inflating the emission list is not free, and this script
    deliberately cannot see that cost -- read it with merge_probe's table.

Usage:
    python compose_integrity_ab.py --composer compose_compound:compose
    python compose_integrity_ab.py --composer compose_relationship:compose --limit 120
"""
import argparse
import collections
import importlib
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


def build(user, composer=None):
    """-> {session_index: [record strings]}"""
    import halumem_run as H
    import propositions as PR
    mem, _ = H.ingest_user(user, cache_path=CACHE)
    nodes = list(mem.g.nodes.values()) + list(mem.g.provisional.values())
    owner = PR.owner_name([{"attr": n["attr"], "value": n["value"]} for n in nodes])

    per = collections.defaultdict(list)
    for nd in nodes:
        for cid in (nd.get("convs") or {}):
            if str(cid).startswith("s") and str(cid)[1:].isdigit():
                per[int(str(cid)[1:])].append(nd)
                break

    out = {}
    for si in range(len(user["sessions"])):
        facts = [{"attr": n["attr"], "value": n["value"],
                  "n_mentions": n.get("n_mentions", 1), "tier": n.get("tier")}
                 for n in per.get(si, [])]
        recs = [p for p in (PR.render(f, owner=owner) for f in facts) if p]
        if composer:
            try:
                extra = composer(facts, owner=owner) or []
            except TypeError:
                extra = composer(facts) or []
            recs = recs + [str(x) for x in extra if str(x).strip()]
        out[si] = recs
    return out


def gold_points(user):
    for si, s in enumerate(user["sessions"]):
        for mp in s.get("memory_points", []):
            if str(mp.get("is_update")) == "True":
                continue          # the update axis has its own harness
            yield si, mp


def judge(items, label):
    from eval_tools import evaluation_for_memory_integrity
    from concurrent.futures import ProcessPoolExecutor, as_completed
    out = {}
    with ProcessPoolExecutor(max_workers=4) as ex:
        fut = {ex.submit(evaluation_for_memory_integrity, blob, mp["memory_content"]): key
               for key, blob, mp in items}
        for i, f in enumerate(as_completed(fut), 1):
            try:
                out[fut[f]] = int((f.result() or {}).get("score"))
            except Exception:
                out[fut[f]] = None
            if i % 50 == 0:
                print(f"  [{label}] {i}/{len(items)}", flush=True)
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
    ap.add_argument("--composer", required=True, help="module:function")
    ap.add_argument("--user", type=int, default=10)
    ap.add_argument("--limit", type=int, default=0,
                    help="judge only the first N gold points (pilot)")
    a = ap.parse_args()

    mod, fn = a.composer.split(":")
    composer = getattr(importlib.import_module(mod), fn)

    user = [json.loads(l) for l in open(DATA, encoding="utf-8")][a.user]
    base = build(user, None)
    comp = build(user, composer)

    nb = sum(len(v) for v in base.values())
    nc = sum(len(v) for v in comp.values())
    print(f"records: atoms {nb}  ->  atoms+compounds {nc}  (+{nc-nb}, "
          f"{(nc-nb)/max(1,nb):+.0%})")
    print("  NB: record count is the denominator of target_accuracy; this "
          "script\n      cannot see that cost -- read it with merge_probe.\n")

    pts = list(gold_points(user))
    if a.limit:
        pts = pts[:a.limit]
    print(f"{len(pts)} non-update gold points to judge, x2 arms\n")

    items_b, items_c = [], []
    for si, mp in pts:
        key = (si, mp.get("index"), mp.get("memory_content"))
        items_b.append((key, "\n".join(base.get(si, [])), mp))
        items_c.append((key, "\n".join(comp.get(si, [])), mp))

    rb = judge(items_b, "atoms")
    rc = judge(items_c, "compounds")

    keys = [k for k, _, _ in items_b if rb.get(k) is not None and rc.get(k) is not None]
    bad = len(pts) - len(keys)
    if bad:
        print(f"  WARNING: {bad} gold points scored None in one arm and are excluded")
    hb = sum(1 for k in keys if rb[k] == 2)
    hc = sum(1 for k in keys if rc[k] == 2)
    print(f"\npaired n={len(keys)}")
    print(f"  atoms      recall {hb/len(keys):7.2%}  ({hb}/{len(keys)})")
    print(f"  +compounds recall {hc/len(keys):7.2%}  ({hc}/{len(keys)})"
          f"   delta {(hc-hb)/len(keys):+.2%}pt")
    b, c, p = mcnemar([(rb[k] == 2, rc[k] == 2) for k in keys])
    print(f"  discordant: atoms-only {b}, compounds-only {c}   "
          f"McNemar exact p={p:.4g}")

    by = collections.defaultdict(lambda: [0, 0, 0])
    for si, mp in pts:
        k = (si, mp.get("index"), mp.get("memory_content"))
        if k not in rb or rb.get(k) is None or rc.get(k) is None:
            continue
        t = by[mp.get("memory_type")]
        t[0] += rb[k] == 2
        t[1] += rc[k] == 2
        t[2] += 1
    print("\n  by memory type:")
    for t, (x, y, n) in sorted(by.items()):
        print(f"    {str(t):<22}{x/n:7.1%} -> {y/n:7.1%}   (n={n})")


if __name__ == "__main__":
    main()
