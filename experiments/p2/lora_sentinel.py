"""Quality sentinel for the extractor LoRA run. Watches OUTPUT, not liveness.

A training run that is merely ALIVE tells you nothing -- the failure modes that
have cost this project time all look healthy from outside. Checks, in the
order a failure would appear:

  NAN         loss went nan/inf. Nothing after this point is recoverable.
  FLAT        train loss has not improved over the last N logged steps. A LoRA
              that is not learning burns an hour and produces a no-op adapter.
  DIVERGING   eval loss rising while train loss falls -- memorising users
              10-19 rather than learning extraction, which is the failure that
              matters most here because the whole point is transfer to 0-9.
  STALL       no new log line for 20 minutes.
"""
import argparse
import json
import os
import re
import sys
import time

NUM = re.compile(r"'(loss|eval_loss)':\s*'?([0-9.eE+-]+)'?")


def scan(path):
    tr, ev = [], []
    if not os.path.exists(path):
        return tr, ev
    for line in open(path, encoding="utf-8", errors="ignore"):
        for k, v in NUM.findall(line):
            try:
                f = float(v)
            except ValueError:
                continue
            (ev if k == "eval_loss" else tr).append(f)
    return tr, ev


def check(path, flat_window=8):
    tr, ev = scan(path)
    out = []
    if any(x != x or x in (float("inf"), float("-inf")) for x in tr + ev):
        out.append(("NAN", "loss went nan/inf -- kill the run"))
    if len(tr) >= flat_window:
        w = tr[-flat_window:]
        if min(w) >= min(tr[:-flat_window] or [float("inf")]):
            out.append(("FLAT", f"train loss has not improved in {flat_window} "
                                f"logs (last {w[-1]:.4f}, best {min(tr):.4f})"))
    if len(ev) >= 3 and ev[-1] > min(ev) * 1.10 and len(tr) > 3 and tr[-1] < tr[0]:
        out.append(("DIVERGING", f"eval loss {ev[-1]:.4f} is >10% above its best "
                                 f"{min(ev):.4f} while train loss still falls -- "
                                 "memorising the training users"))
    if os.path.exists(path):
        age = time.time() - os.path.getmtime(path)
        if age > 20 * 60:
            out.append(("STALL", f"no log write for {age/60:.0f} min"))
    return out, tr, ev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("log")
    ap.add_argument("--interval", type=int, default=300)
    ap.add_argument("--once", action="store_true")
    a = ap.parse_args()
    while True:
        bad, tr, ev = check(a.log)
        stamp = time.strftime("%H:%M")
        for name, msg in bad:
            print(f"[{stamp}] ANOMALY {name}: {msg}", flush=True)
        if a.once:
            print(f"[{stamp}] {len(tr)} train logs, {len(ev)} evals; "
                  f"train {tr[-1] if tr else '-'} eval {ev[-1] if ev else '-'}")
            return 1 if bad else 0
        if bad:
            return 1
        time.sleep(a.interval)


if __name__ == "__main__":
    sys.exit(main())
