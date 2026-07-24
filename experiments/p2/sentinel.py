"""Sentinel: monitors the official HaluMem run + dev extraction caches for
OUTPUT-QUALITY anomalies, not just liveness.

Real incidents this exists to catch (see HANDOVER / task notes):
  1. An official run silently produced degenerate output for 2 days --
     163/164 answers were the bare string "Unknown." in per-user checkpoint
     JSONs. Liveness watchers never noticed because the process was alive
     and the log kept growing -- it was just producing garbage.
  2. A judge-server outage made the harness error-default 19 users in ~33s
     each (real users take hours). Visible only in log timestamp deltas,
     not in whether the process was "running".
  3. pgrep-based process checks false-positived on their OWN shell's
     command line (e.g. a grep/pgrep invocation that contains the target
     script name as a string literal). Fixed here by reading /proc/*/cmdline
     directly and matching on whole argv elements (equals/endswith), never
     substring-matching the whole command line.

Two modes:
  report            -- one status table, exit 0.
  watch --interval N -- loop forever, print one status line per pass, exit
                         non-zero with "ANOMALY: <what>" on the first
                         detected anomaly (the caller uses process exit as
                         the wake-up signal).

Every check is individually try/excepted (in `run_checks`) so one broken or
missing artifact can never crash the sentinel or hide the other checks.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from typing import Optional

HOME = os.path.expanduser("~")
DEFAULT_HALUMEM = os.path.join(HOME, "rg_private", "halumem")
DEFAULT_OFFICIAL = os.path.join(DEFAULT_HALUMEM, "official")
DEFAULT_EVAL_RESULTS = os.path.join(
    DEFAULT_OFFICIAL, "HaluMem", "eval", "results", "rgp2-default"
)
DEFAULT_DEV_DIR = os.path.join(DEFAULT_HALUMEM, "dev")

RETRY_WINDOW_LINES = 200
RETRY_STORM_THRESHOLD = 50
EVAL_LOG_STALL_SECONDS = 20 * 60

UNKNOWN_RATE_ANOMALY = 0.85
HALLUCINATION_RATE_ANOMALY = 0.15
NONE_RATE_ANOMALY = 0.10

FAST_FINISH_SECONDS = 600

RAM_CRUNCH_GIB = 1.0
DISK_CRUNCH_GIB = 5.0
SWAP_USED_PCT_ANOMALY = 0.90

CACHE_ACTIVE_WINDOW_SECONDS = 10 * 60
CACHE_SAMPLE_LINES = 200
CACHE_PARSE_RATE_ANOMALY = 0.90  # below this -> corruption
CACHE_EMPTY_RATE_ANOMALY = 0.90  # above this -> degenerate extraction

FINISHED_USER_RE = re.compile(
    r"Finished user\s+(\S+)\s+\((\d+)\),\s*elapsed\s+([\d.]+)s"
)


@dataclass
class CheckResult:
    name: str
    status: str
    anomaly: Optional[str] = None
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.anomaly is None

    def line(self) -> str:
        tag = "ANOMALY" if self.anomaly else "ok"
        msg = self.anomaly or self.status
        extra = f" -- {self.detail}" if self.detail else ""
        return f"[{tag:7}] {self.name}: {msg}{extra}"


def _fmt_anomaly(check_name: str, anomaly: str) -> str:
    return f"ANOMALY: {check_name}: {anomaly}"


# --------------------------------------------------------------------------
# 1. Official eval checks
# --------------------------------------------------------------------------

def _bare_unknown(resp) -> bool:
    return isinstance(resp, str) and resp.strip() == "Unknown."


def analyze_checkpoint(path: str) -> dict:
    """Parse a tmp2/*.json checkpoint and compute rates for
    question_answering_records. Returns a dict of stats; raises on
    malformed input (caller decides how to handle)."""
    with open(path) as f:
        data = json.load(f)
    records = data.get("question_answering_records", []) or []
    n = len(records)
    if n == 0:
        return {"n": 0, "unknown_rate": 0.0, "hallucination_rate": 0.0,
                "none_rate": 0.0}
    unknown = sum(1 for r in records if _bare_unknown(r.get("system_response")))
    hallucination = sum(1 for r in records if r.get("result_type") == "Hallucination")
    none_ct = sum(1 for r in records if r.get("result_type") is None)
    return {
        "n": n,
        "unknown_rate": unknown / n,
        "hallucination_rate": hallucination / n,
        "none_rate": none_ct / n,
    }


def check_official_eval(
    halumem_dir: str = DEFAULT_HALUMEM,
    official_dir: Optional[str] = None,
    eval_results_dir: Optional[str] = None,
    checkpoint_cache: Optional[dict] = None,
    now: Optional[float] = None,
) -> CheckResult:
    """checkpoint_cache: {(path, mtime): stats} -- caller-owned, so repeated
    `watch` passes only re-parse checkpoints that actually changed."""
    name = "official_eval"
    official_dir = official_dir or os.path.join(halumem_dir, "official")
    eval_results_dir = eval_results_dir or os.path.join(
        official_dir, "HaluMem", "eval", "results", "rgp2-default"
    )
    now = now if now is not None else time.time()
    if checkpoint_cache is None:
        checkpoint_cache = {}

    paused_marker = os.path.join(official_dir, ".OFFICIAL_PAUSED")
    complete_marker = os.path.join(halumem_dir, "OFFICIAL_COMPLETE")

    if os.path.exists(paused_marker):
        return CheckResult(name, "paused")
    if os.path.exists(complete_marker):
        return CheckResult(name, "complete")

    eval_log = os.path.join(official_dir, "eval.log")
    if not os.path.exists(eval_log):
        return CheckResult(name, "no eval.log found (not started?)")

    log_mtime = os.path.getmtime(eval_log)
    age_s = now - log_mtime
    if age_s > EVAL_LOG_STALL_SECONDS:
        return CheckResult(
            name, "stalled",
            anomaly="eval stalled",
            detail=f"eval.log last grew {age_s/60:.1f} min ago",
        )

    with open(eval_log, "r", errors="replace") as f:
        content = f.read()
    lines = content.split("\n")
    tail = lines[-RETRY_WINDOW_LINES:]
    retry_lines = sum(1 for l in tail if "Retrying" in l)
    if retry_lines > RETRY_STORM_THRESHOLD:
        return CheckResult(
            name, "retry storm",
            anomaly="retry storm (server down?)",
            detail=f"{retry_lines}/{len(tail)} recent lines contain 'Retrying'",
        )

    # Per-checkpoint output-quality checks.
    for path in sorted(glob.glob(os.path.join(eval_results_dir, "tmp2", "*.json"))):
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            continue
        cache_key = (path, mtime)
        if cache_key in checkpoint_cache:
            stats = checkpoint_cache[cache_key]
        else:
            stats = analyze_checkpoint(path)
            checkpoint_cache[cache_key] = stats

        user = os.path.basename(path)
        if stats["unknown_rate"] > UNKNOWN_RATE_ANOMALY:
            return CheckResult(
                name, "degenerate", anomaly="degenerate abstention",
                detail=(f"{user}: {stats['unknown_rate']*100:.1f}% bare "
                        f"'Unknown.' responses (n={stats['n']})"),
            )
        if stats["hallucination_rate"] > HALLUCINATION_RATE_ANOMALY:
            return CheckResult(
                name, "hallucinating", anomaly="hallucination rate too high",
                detail=(f"{user}: {stats['hallucination_rate']*100:.1f}% "
                        f"Hallucination (n={stats['n']})"),
            )
        if stats["none_rate"] > NONE_RATE_ANOMALY:
            return CheckResult(
                name, "unscored", anomaly="result_type None rate too high",
                detail=(f"{user}: {stats['none_rate']*100:.1f}% None "
                        f"result_type (n={stats['n']})"),
            )

    # Finished-user pacing: consecutive elapsed deltas that are suspiciously
    # small mean users are error-defaulting instead of actually running.
    matches = FINISHED_USER_RE.findall(content)
    elapsed = [float(m[2]) for m in matches]
    users = [m[0] for m in matches]
    for i in range(1, len(elapsed)):
        diff = abs(elapsed[i] - elapsed[i - 1])
        if diff < FAST_FINISH_SECONDS:
            return CheckResult(
                name, "fast finishes",
                anomaly="users finishing in minutes (error-defaulting)",
                detail=(f"{users[i-1]} -> {users[i]}: elapsed delta "
                        f"{diff:.1f}s"),
            )

    n_checkpoints = len(glob.glob(os.path.join(eval_results_dir, "tmp2", "*.json")))
    return CheckResult(name, f"running ({n_checkpoints} users checkpointed)")


# --------------------------------------------------------------------------
# 2. Process checks
# --------------------------------------------------------------------------

TARGET_SCRIPTS = {
    "evaluation.py": "evaluation.py",
    "llama_cpp.server": "llama_cpp.server",
    "dev_set.py": "dev_set.py",
}


def _read_cmdline(pid: str) -> list:
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            raw = f.read()
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return []
    if not raw:
        return []
    return [p for p in raw.split(b"\0") if p]


def _ancestor_pids(pid: int) -> set:
    """Walk the ppid chain from `pid` up to pid 1 (or until /proc is
    unreadable), returning the set of ancestor pids as strings."""
    ancestors = set()
    cur = pid
    seen = set()
    while cur and cur not in seen:
        seen.add(cur)
        try:
            with open(f"/proc/{cur}/stat", "r") as f:
                stat = f.read()
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            break
        # cmd name is in parens and may contain spaces/')' -- find the
        # last ')' to skip past it before splitting the rest by whitespace.
        rparen = stat.rfind(")")
        if rparen == -1:
            break
        fields = stat[rparen + 2:].split()
        if len(fields) < 2:
            break
        ppid = int(fields[1])
        if ppid <= 1:
            ancestors.add(str(ppid))
            break
        ancestors.add(str(ppid))
        cur = ppid
    return ancestors


def find_running_targets(exclude_pids: Optional[set] = None) -> dict:
    """Returns {target_name: bool} for each TARGET_SCRIPTS entry, by
    enumerating /proc/*/cmdline directly and matching whole argv elements
    (an argument that equals or endswith the target string) -- never
    substring-matching the joined command line, which is what caused the
    pgrep false-positive incident (a shell command that merely *mentions*
    the script name inside a larger string argument, e.g. a pgrep -f
    pattern or an echoed heredoc, does NOT match here)."""
    exclude_pids = exclude_pids or set()
    found = {name: False for name in TARGET_SCRIPTS}
    try:
        pids = [p for p in os.listdir("/proc") if p.isdigit()]
    except OSError:
        return found
    for pid in pids:
        if pid in exclude_pids:
            continue
        argv = _read_cmdline(pid)
        if not argv:
            continue
        for arg in argv:
            try:
                arg_s = arg.decode("utf-8", errors="replace")
            except AttributeError:
                arg_s = arg
            for target_name, needle in TARGET_SCRIPTS.items():
                if found[target_name]:
                    continue
                if arg_s == needle or arg_s.endswith(needle):
                    found[target_name] = True
        if all(found.values()):
            break
    return found


def check_processes(exclude_pids: Optional[set] = None,
                     official_dir: Optional[str] = None) -> CheckResult:
    name = "processes"
    self_pid = os.getpid()
    exclude = set(exclude_pids) if exclude_pids else set()
    exclude.add(str(self_pid))
    exclude |= _ancestor_pids(self_pid)

    running = find_running_targets(exclude_pids=exclude)
    official_dir = official_dir or DEFAULT_OFFICIAL
    paused_marker = os.path.join(official_dir, ".OFFICIAL_PAUSED")
    is_paused = os.path.exists(paused_marker)

    status = ", ".join(
        f"{k}={'up' if v else 'down'}" for k, v in sorted(running.items())
    )

    if running.get("evaluation.py") and is_paused:
        return CheckResult(name, status, anomaly="paused but running",
                            detail="evaluation.py is running while "
                                   ".OFFICIAL_PAUSED marker exists")
    if running.get("evaluation.py") and not running.get("llama_cpp.server"):
        return CheckResult(
            name, status,
            anomaly="eval without judge server -- will error-default",
            detail="evaluation.py is running but llama_cpp.server is not",
        )
    return CheckResult(name, status)


# --------------------------------------------------------------------------
# 3. Host checks
# --------------------------------------------------------------------------

def _read_meminfo(path: str = "/proc/meminfo") -> dict:
    info = {}
    with open(path) as f:
        for line in f:
            parts = line.split(":")
            if len(parts) != 2:
                continue
            key = parts[0].strip()
            val = parts[1].strip().split()[0]  # kB
            try:
                info[key] = int(val) * 1024  # bytes
            except ValueError:
                pass
    return info


def check_host(meminfo_path: str = "/proc/meminfo",
                disk_path: str = "/home") -> CheckResult:
    name = "host"
    details = []

    try:
        meminfo = _read_meminfo(meminfo_path)
        available = meminfo.get("MemAvailable")
        if available is not None:
            avail_gib = available / (1024 ** 3)
            details.append(f"RAM avail {avail_gib:.2f} GiB")
            if avail_gib < RAM_CRUNCH_GIB:
                return CheckResult(name, "; ".join(details),
                                    anomaly="RAM crunch")
        swap_total = meminfo.get("SwapTotal", 0)
        swap_free = meminfo.get("SwapFree", 0)
        if swap_total > 0:
            swap_used_pct = (swap_total - swap_free) / swap_total
            details.append(f"swap used {swap_used_pct*100:.0f}%")
            if swap_used_pct > SWAP_USED_PCT_ANOMALY:
                return CheckResult(name, "; ".join(details),
                                    anomaly="swap crunch")
    except OSError:
        details.append("meminfo unavailable")

    try:
        st = os.statvfs(disk_path)
        free_gib = (st.f_bavail * st.f_frsize) / (1024 ** 3)
        details.append(f"disk({disk_path}) free {free_gib:.2f} GiB")
        if free_gib < DISK_CRUNCH_GIB:
            return CheckResult(name, "; ".join(details), anomaly="disk crunch")
    except OSError:
        details.append("disk stat unavailable")

    return CheckResult(name, "; ".join(details) or "unavailable")


# --------------------------------------------------------------------------
# 4. Dev cache checks
# --------------------------------------------------------------------------

def analyze_cache_sample(path: str, sample_lines: int = CACHE_SAMPLE_LINES) -> dict:
    with open(path, "r", errors="replace") as f:
        lines = f.readlines()
    tail = [l for l in lines[-sample_lines:] if l.strip()]
    n = len(tail)
    if n == 0:
        return {"n": 0, "parse_rate": 1.0, "empty_rate": 0.0}
    parsed = 0
    empty = 0
    for l in tail:
        try:
            d = json.loads(l)
        except (json.JSONDecodeError, ValueError):
            continue
        parsed += 1
        if d.get("f") == []:
            empty += 1
    parse_rate = parsed / n
    empty_rate = (empty / parsed) if parsed else 0.0
    return {"n": n, "parse_rate": parse_rate, "empty_rate": empty_rate}


def check_dev_caches(dev_dir: str = DEFAULT_DEV_DIR,
                      now: Optional[float] = None) -> CheckResult:
    name = "dev_caches"
    now = now if now is not None else time.time()
    paths = sorted(glob.glob(os.path.join(dev_dir, "cache_*.jsonl")))
    active = []
    for path in paths:
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            continue
        if now - mtime <= CACHE_ACTIVE_WINDOW_SECONDS:
            active.append(path)

    if not active:
        return CheckResult(name, f"no actively-growing caches ({len(paths)} total)")

    checked = []
    for path in active:
        stats = analyze_cache_sample(path)
        base = os.path.basename(path)
        checked.append(f"{base} n={stats['n']} parse={stats['parse_rate']*100:.0f}% "
                        f"empty={stats['empty_rate']*100:.0f}%")
        if stats["n"] > 0 and stats["parse_rate"] < CACHE_PARSE_RATE_ANOMALY:
            return CheckResult(
                name, "; ".join(checked), anomaly="cache corruption",
                detail=f"{base}: parse rate {stats['parse_rate']*100:.1f}%",
            )
        if stats["n"] > 0 and stats["empty_rate"] > CACHE_EMPTY_RATE_ANOMALY:
            return CheckResult(
                name, "; ".join(checked), anomaly="degenerate extraction",
                detail=f"{base}: empty-fact rate {stats['empty_rate']*100:.1f}%",
            )

    return CheckResult(name, "; ".join(checked))


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------

@dataclass
class SentinelPaths:
    halumem_dir: str = DEFAULT_HALUMEM
    official_dir: Optional[str] = None
    eval_results_dir: Optional[str] = None
    dev_dir: Optional[str] = None
    meminfo_path: str = "/proc/meminfo"
    disk_path: str = "/home"


def run_checks(paths: SentinelPaths,
                checkpoint_cache: Optional[dict] = None) -> list:
    """Runs every check, each individually wrapped in try/except so a
    single broken/missing artifact can never take the others down."""
    checkpoint_cache = checkpoint_cache if checkpoint_cache is not None else {}
    results = []

    checks: list = [
        ("official_eval", lambda: check_official_eval(
            halumem_dir=paths.halumem_dir,
            official_dir=paths.official_dir,
            eval_results_dir=paths.eval_results_dir,
            checkpoint_cache=checkpoint_cache,
        )),
        ("processes", lambda: check_processes(official_dir=paths.official_dir)),
        ("host", lambda: check_host(
            meminfo_path=paths.meminfo_path, disk_path=paths.disk_path)),
        ("dev_caches", lambda: check_dev_caches(
            dev_dir=paths.dev_dir or os.path.join(paths.halumem_dir, "dev"))),
    ]

    for cname, fn in checks:
        try:
            results.append(fn())
        except Exception as e:  # noqa: BLE001 -- deliberately broad, see docstring
            results.append(CheckResult(cname, "check errored",
                                        detail=f"{type(e).__name__}: {e}"))
    return results


def print_report(results: list) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"=== sentinel report {ts} ===")
    for r in results:
        print(r.line())


def first_anomaly(results: list) -> Optional[CheckResult]:
    for r in results:
        if r.anomaly:
            return r
    return None


def cmd_report(paths: SentinelPaths) -> int:
    results = run_checks(paths)
    print_report(results)
    anomaly = first_anomaly(results)
    return 1 if anomaly else 0


def cmd_watch(paths: SentinelPaths, interval: int) -> int:
    checkpoint_cache: dict = {}
    while True:
        results = run_checks(paths, checkpoint_cache=checkpoint_cache)
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        anomaly = first_anomaly(results)
        summary = "; ".join(
            f"{r.name}={r.anomaly or r.status}" for r in results
        )
        print(f"[{ts}] {summary}")
        sys.stdout.flush()
        if anomaly:
            print(_fmt_anomaly(anomaly.name, anomaly.anomaly) +
                  (f" -- {anomaly.detail}" if anomaly.detail else ""))
            return 1
        time.sleep(interval)


def build_paths_from_args(args) -> SentinelPaths:
    halumem_dir = args.halumem_dir
    return SentinelPaths(
        halumem_dir=halumem_dir,
        official_dir=os.path.join(halumem_dir, "official"),
        dev_dir=os.path.join(halumem_dir, "dev"),
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--halumem-dir", dest="halumem_dir",
                         default=DEFAULT_HALUMEM,
                         help="base dir containing official/ and dev/")
    sub = parser.add_subparsers(dest="mode", required=True)

    sub.add_parser("report", help="print a status table and exit")

    watch_p = sub.add_parser("watch", help="loop forever, one line per pass")
    watch_p.add_argument("--interval", type=int, default=1800,
                          help="seconds between passes (default 1800)")

    args = parser.parse_args(argv)
    paths = build_paths_from_args(args)

    if args.mode == "report":
        return cmd_report(paths)
    elif args.mode == "watch":
        return cmd_watch(paths, args.interval)
    parser.error(f"unknown mode {args.mode}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
