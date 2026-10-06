"""Quality sentinel for teacher.jsonl: exits 1 on an anomaly, 0 when done."""
import json, sys, time, os
p = os.path.expanduser("~/jpwork/distil/teacher.jsonl")
last_n, last_t = 0, time.time()
while True:
    rows = [json.loads(l) for l in open(p)]
    tail = rows[-160:]
    n = len(tail)
    if n >= 48:
        empty = sum(not r["notes"] for r in tail) / n
        drop = sum(len(r["dropped"]) for r in tail) / max(1, sum(len(r["dropped"]) + len(r["notes"]) for r in tail))
        loop = sum(len(r["raw"].splitlines()) > 3 and len(set(r["raw"].splitlines())) < 0.6 * len(r["raw"].splitlines()) for r in tail) / n
        clar = sum("clarinet" in r["raw"] for r in tail) / n
        bad = [k for k, v, lim in (("empty", empty, .6), ("dropped", drop, .35), ("loops", loop, .05), ("clarinet", clar, .1)) if v > lim]
        if bad:
            print(f"ANOMALY {bad} at {len(rows)}: empty {empty:.2f} dropped {drop:.2f} loops {loop:.2f} clarinet {clar:.2f}"); sys.exit(1)
    if "teacher done" in open(os.path.expanduser("~/jpwork/distil/teacher.log")).read():
        print("done", len(rows)); sys.exit(0)
    if len(rows) > last_n:
        last_n, last_t = len(rows), time.time()
    elif time.time() - last_t > 1500:
        print("STALL at", len(rows)); sys.exit(1)
    time.sleep(120)
