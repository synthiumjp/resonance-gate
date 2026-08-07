"""Quality sentinel for the S5 judged A/B. Watches OUTPUT, not liveness.

sentinel.py covers the official rgp2-default run; S5 writes to its own results
dirs and has failure modes of its own, so it gets its own checks rather than a
widened default path. The incidents these are shaped by are the same ones
sentinel.py's docstring records: a run that produced 163/164 bare "Unknown."
answers for two days while looking perfectly healthy, and a judge-server outage
that error-defaulted whole users in ~33s each.

Checks, in the order a failure would actually appear:

  ARMS_DIFFER   the two stage-1 artifacts must emit different memory counts.
                A silent env-var failure (the .env line-32 incident, entry 181)
                makes both arms identical, and every downstream number would
                then be a null by construction. This is the single most
                valuable check here.
  UNKNOWN_RATE  fraction of QA responses that are a bare "Unknown." Degenerate
                composer output looks exactly like a healthy run from outside.
  EMPTY_EXTRACT fraction of sessions emitting nothing. The judge scores those
                0 without making a call, so a broken cache path would show up
                as a fast, cheap, entirely wrong run.
  JUDGE_NONE    fraction of judged records whose score is None -- the judge
                returned unparseable JSON. Above ~10% the aggregate is being
                computed on a minority of the data.
  FAST_CHUNK    a tmp2 chunk written in under 60s. Real chunks take minutes;
                a fast one means the harness error-defaulted it.
  STALL         no log write for over 20 minutes.

Usage:
    python s5_sentinel.py report
    python s5_sentinel.py watch --interval 900     # exits non-zero on anomaly
"""
import argparse
import glob
import json
import os
import sys
import time

SP = ("/tmp/claude-1000/-home-jp-rg/"
      "320688fb-20b4-45ea-b1e7-d0fbb0e3ca6c/scratchpad/s5")
EV = os.path.expanduser("~/rg_private/halumem/official/HaluMem/eval")

UNKNOWN_RATE_ANOMALY = 0.85
EMPTY_EXTRACT_ANOMALY = 0.50
JUDGE_NONE_ANOMALY = 0.10
FAST_CHUNK_SECONDS = 60
STALL_SECONDS = 20 * 60


def _artifact(arm):
    p = f"{EV}/results/rgp2-s5-{arm}/rgp2_eval_results.jsonl"
    if not os.path.exists(p) or os.path.getsize(p) == 0:
        return None
    return json.loads(open(p, encoding="utf-8").readline())


def check_arms_differ():
    n = {}
    for arm in ("base", "all"):
        u = _artifact(arm)
        if u is None:
            return "pending", f"{arm} artifact not built yet"
        n[arm] = sum(len(s.get("extracted_memories", [])) for s in u["sessions"])
    if n["base"] == n["all"]:
        return "ANOMALY", (f"both arms emitted {n['base']} memories -- the "
                           "all-turns flag did not take")
    return "ok", f"base={n['base']} all={n['all']} (differ by {n['all']-n['base']})"


def check_stage1_quality():
    out = []
    for arm in ("base", "all"):
        u = _artifact(arm)
        if u is None:
            out.append(("pending", f"{arm}: not built"))
            continue
        sess = u["sessions"]
        with_mp = [s for s in sess if "extracted_memories" in s]
        empty = sum(1 for s in with_mp if not s["extracted_memories"])
        qs = [q for s in sess for q in s.get("questions", [])]
        unk = sum(1 for q in qs
                  if str(q.get("system_response", "")).strip().rstrip(".").lower()
                  == "unknown")
        er = empty / max(1, len(with_mp))
        ur = unk / max(1, len(qs))
        bad = []
        if er >= EMPTY_EXTRACT_ANOMALY:
            bad.append(f"EMPTY_EXTRACT {er:.1%}")
        if qs and ur >= UNKNOWN_RATE_ANOMALY:
            bad.append(f"UNKNOWN_RATE {ur:.1%}")
        out.append((("ANOMALY" if bad else "ok"),
                    f"{arm}: {len(with_mp)} sessions, empty {er:.1%}, "
                    f"{len(qs)} questions, bare-Unknown {ur:.1%}"
                    + (" <- " + ", ".join(bad) if bad else "")))
    return out


def check_judge_chunks():
    out = []
    for arm in ("base", "all"):
        files = sorted(glob.glob(f"{EV}/results/rgp2-s5-{arm}-j/tmp2/*.json"))
        if not files:
            out.append(("pending", f"{arm}: no chunks judged yet"))
            continue
        none_n = tot = 0
        for f in files:
            try:
                d = json.load(open(f, encoding="utf-8"))
            except Exception:
                continue
            for key, field in (("memory_integrity_records", "memory_integrity_score"),
                               ("memory_accuracy_records", "memory_accuracy_score")):
                for r in d.get(key, []):
                    tot += 1
                    none_n += r.get(field) is None
        rate = none_n / max(1, tot)
        # a chunk written within FAST_CHUNK_SECONDS of the previous one is the
        # error-default signature
        times = sorted(os.path.getmtime(f) for f in files)
        fast = sum(1 for a, b in zip(times, times[1:]) if b - a < FAST_CHUNK_SECONDS)
        bad = []
        if rate >= JUDGE_NONE_ANOMALY:
            bad.append(f"JUDGE_NONE {rate:.1%}")
        if fast:
            bad.append(f"FAST_CHUNK x{fast}")
        out.append((("ANOMALY" if bad else "ok"),
                    f"{arm}: {len(files)} chunks, {tot} judged records, "
                    f"None {rate:.1%}" + (" <- " + ", ".join(bad) if bad else "")))
    return out


def check_stall():
    logs = glob.glob(f"{SP}/stage*.log") + [f"{SP}/driver.log"]
    logs = [p for p in logs if os.path.exists(p)]
    if not logs:
        return "pending", "no logs yet"
    if os.path.exists(f"{SP}/S5_DONE"):
        return "ok", "run complete"
    newest = max(os.path.getmtime(p) for p in logs)
    age = time.time() - newest
    if age > STALL_SECONDS:
        return "ANOMALY", f"no log write for {age/60:.0f} min"
    return "ok", f"last log write {age/60:.1f} min ago"


def run_checks():
    res = [("ARMS_DIFFER",) + check_arms_differ()]
    for st, msg in check_stage1_quality():
        res.append(("STAGE1", st, msg))
    for st, msg in check_judge_chunks():
        res.append(("JUDGE", st, msg))
    res.append(("STALL",) + check_stall())
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    sub.add_parser("report")
    w = sub.add_parser("watch")
    w.add_argument("--interval", type=int, default=900)
    a = ap.parse_args(argv)

    while True:
        res = run_checks()
        stamp = time.strftime("%H:%M")
        for name, st, msg in res:
            if st == "ANOMALY":
                print(f"[{stamp}] ANOMALY {name}: {msg}", flush=True)
            elif a.mode == "report":
                print(f"[{stamp}] {st:8s} {name}: {msg}", flush=True)
        if any(st == "ANOMALY" for _, st, _ in res):
            return 1
        if a.mode == "report":
            return 0
        if os.path.exists(f"{SP}/S5_DONE"):
            print(f"[{stamp}] S5 complete, sentinel exiting clean", flush=True)
            return 0
        time.sleep(a.interval)


if __name__ == "__main__":
    sys.exit(main())
