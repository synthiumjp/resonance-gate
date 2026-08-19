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
# tqdm writes the progress bar to STDERR (unbuffered) while Trainer's loss dicts
# go to STDOUT, which python block-buffers under nohup -- so losses arrive in
# ~8KB chunks and lag the bar badly (v3's step-25 log appeared at step 200).
# Without a progress signal a genuine early stall is indistinguishable from
# buffering, which is a blind spot the first version of this file had.
STEP = re.compile(r"(\d+)/(\d+)\s*\[")


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


def steps(path):
    """(current, total) from the newest tqdm bar, or None."""
    if not os.path.exists(path):
        return None
    raw = open(path, encoding="utf-8", errors="ignore").read()[-20000:]
    m = STEP.findall(raw.replace("\r", "\n"))
    return (int(m[-1][0]), int(m[-1][1])) if m else None


_LAST = {}


def check(path, flat_window=8):
    tr, ev = scan(path)
    out = []
    # progress-based stall detection, independent of the buffered loss stream
    st = steps(path)
    if st:
        prev = _LAST.get(path)
        now = time.time()
        if prev and st[0] == prev[0] and now - prev[1] > 15 * 60:
            out.append(("NO_PROGRESS",
                        f"step {st[0]}/{st[1]} unchanged for "
                        f"{(now-prev[1])/60:.0f} min"))
        if not prev or st[0] != prev[0]:
            _LAST[path] = (st[0], now)
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
    # A COMPLETED run stops writing, so an unqualified staleness check fires
    # on success -- which it did on adapter-v1, reporting STALL 63 minutes
    # after the run finished cleanly. Check for the completion marker first,
    # the same way s5_sentinel checks S5_DONE.
    done = False
    if os.path.exists(path):
        with open(path, encoding="utf-8", errors="ignore") as fh:
            done = "saved adapter to" in fh.read()[-4000:]
    if os.path.exists(path) and not done:
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
            st = steps(a.log)
            print(f"[{stamp}] step {st[0]}/{st[1]}" if st else f"[{stamp}] no bar",
                  f"| {len(tr)} train logs, {len(ev)} evals; "
                  f"train {tr[-1] if tr else '-'} eval {ev[-1] if ev else '-'}")
            return 1 if bad else 0
        if bad:
            return 1
        time.sleep(a.interval)


if __name__ == "__main__":
    sys.exit(main())
