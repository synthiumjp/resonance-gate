"""Quality sentinel for a release re-measurement (tools/release_measure2.sh)
on the Mac. Checks what the run writes, not only that it is alive:

  - the log: a step that reports "failed", a traceback, a server that is down
  - LoCoMo answer files written by this run: too many empty answers, too many
    "I don't know"s, too few judged correct (a broken reader or judge)
  - progress: no file of the run written for STALL minutes
  - the run gone before its "release measure 2 done" line

    python3 tools/release_sentinel.py --tree ~/jpwork/sdr-release-<c> --log ~/jpwork/release7.log

Exit 0: the run finished and nothing looked wrong; 1: an anomaly (printed as
"ANOMALY: ..."); 2: still running and nothing wrong yet. A loop on another
machine calls it every few minutes and stops on 0 or 1.
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys
import time

STALL = 45 * 60
REFUSAL = re.compile(r"(?i)\b(?:i don'?t know|not mentioned|no information|unknown|"
                     r"cannot (?:be )?determine|not (?:stated|specified))\b")
LOG_BAD = re.compile(r"Traceback|\bfailed\b|is down|Killed|MemoryError|No space left")


def anomaly(msg):
    print(f"ANOMALY: {msg}")
    return 1


def running():
    out = subprocess.run(["ps", "-axo", "pid=,command="], capture_output=True, text=True).stdout
    me = os.getpid()
    for line in out.splitlines():
        pid, _, cmd = line.strip().partition(" ")
        if pid.isdigit() and int(pid) != me and re.search(r"(?:^|\s)bash\s+\S*release_measure2\.sh\b", cmd):
            return True
    return False


def check_answers(path):
    rows = []
    try:
        for line in open(path, encoding="utf-8", errors="replace"):
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
    except OSError:
        return None
    if len(rows) < 100:
        return None
    empty = sum(not str(r.get("pred") or "").strip() for r in rows) / len(rows)
    refused = sum(bool(REFUSAL.search(str(r.get("pred") or ""))) for r in rows) / len(rows)
    judged = [r for r in rows if r.get("label")]
    correct = sum(r["label"] == "CORRECT" for r in judged) / len(judged) if judged else None
    name = os.path.relpath(path)
    if empty > 0.05:
        return f"{name}: {empty:.0%} empty answers of {len(rows)}"
    if refused > 0.6:
        return f"{name}: {refused:.0%} of {len(rows)} answers say they do not know"
    if correct is not None and len(judged) >= 200 and correct < 0.3:
        return f"{name}: only {correct:.0%} of {len(judged)} judged correct"
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", required=True)
    ap.add_argument("--log", required=True)
    a = ap.parse_args()
    tree, log = os.path.expanduser(a.tree), os.path.expanduser(a.log)
    start = os.path.getmtime(os.path.join(tree, "COMMIT"))
    try:
        text = open(log, encoding="utf-8", errors="replace").read()
    except OSError:
        return anomaly(f"no log at {log}")
    for line in text.splitlines():
        if LOG_BAD.search(line) and "0 failed" not in line:
            return anomaly(f"log: {line.strip()[:200]}")
    for p in glob.glob(os.path.join(tree, "bench", "locomo", "results", "*", "ans_*.jsonl")):
        if os.path.getmtime(p) >= start:
            bad = check_answers(p)
            if bad:
                return anomaly(bad)
    done = "release measure 2 done" in text
    newest = max([os.path.getmtime(log)] + [
        os.path.getmtime(p) for p in glob.glob(os.path.join(tree, "bench", "**", "*"), recursive=True)
        if os.path.isfile(p)] + [
        os.path.getmtime(p) for p in glob.glob(os.path.expanduser("~/jpwork/lme/*")) +
        glob.glob(os.path.expanduser("~/jpwork/halumem_release*.log"))])
    last = text.strip().splitlines()[-1][:120] if text.strip() else "(empty)"
    if done:
        print(f"done: {last}")
        return 0
    if not running():
        return anomaly(f"the run is gone without its done line; last: {last}")
    if time.time() - newest > STALL:
        return anomaly(f"nothing written for {int((time.time() - newest) / 60)} minutes; last: {last}")
    print(f"running, {int((time.time() - newest) / 60)} min since the last write; last: {last}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
