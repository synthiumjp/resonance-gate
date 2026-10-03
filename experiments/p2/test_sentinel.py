"""Sentinel tests: synthetic fixtures under tmp_path exercise every anomaly
rule (and the healthy path) without touching any real pipeline artifact."""

import json
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import sentinel as S


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _mk_official(tmp_path, name="official"):
    official = tmp_path / name
    (official / "HaluMem" / "eval" / "results" / "rgp2-default" / "tmp2").mkdir(
        parents=True
    )
    return official


def _write_eval_log(official, text, mtime=None):
    log = official / "eval.log"
    log.write_text(text)
    if mtime is not None:
        os.utime(log, (mtime, mtime))
    return log


def _qa_record(system_response="Manager", result_type="Correct"):
    return {
        "question": "q",
        "answer": "a",
        "system_response": system_response,
        "result_type": result_type,
    }


def _write_checkpoint(official, user_uuid, records, mtime=None):
    path = (
        official
        / "HaluMem"
        / "eval"
        / "results"
        / "rgp2-default"
        / "tmp2"
        / f"{user_uuid}.json"
    )
    path.write_text(json.dumps({"question_answering_records": records}))
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def _healthy_records(n=50):
    out = []
    for i in range(n):
        out.append(_qa_record(system_response=f"answer {i}", result_type="Correct"))
    return out


# --------------------------------------------------------------------------
# official eval: paused / complete
# --------------------------------------------------------------------------

def test_paused_marker_skips_everything(tmp_path):
    halumem = tmp_path
    official = _mk_official(halumem)
    (official / ".OFFICIAL_PAUSED").write_text("")
    # Deliberately broken eval.log / no checkpoints -- must not matter.
    r = S.check_official_eval(halumem_dir=str(halumem), official_dir=str(official))
    assert r.status == "paused"
    assert r.ok


def test_complete_marker(tmp_path):
    halumem = tmp_path
    official = _mk_official(halumem)
    (halumem / "OFFICIAL_COMPLETE").write_text("")
    r = S.check_official_eval(halumem_dir=str(halumem), official_dir=str(official))
    assert r.status == "complete"
    assert r.ok


def test_paused_takes_priority_over_complete(tmp_path):
    halumem = tmp_path
    official = _mk_official(halumem)
    (official / ".OFFICIAL_PAUSED").write_text("")
    (halumem / "OFFICIAL_COMPLETE").write_text("")
    r = S.check_official_eval(halumem_dir=str(halumem), official_dir=str(official))
    assert r.status == "paused"


# --------------------------------------------------------------------------
# official eval: stall / retry storm
# --------------------------------------------------------------------------

def test_eval_log_stall_detected(tmp_path):
    halumem = tmp_path
    official = _mk_official(halumem)
    old = time.time() - 25 * 60  # 25 min ago > 20 min threshold
    _write_eval_log(official, "some log content\n", mtime=old)
    r = S.check_official_eval(halumem_dir=str(halumem), official_dir=str(official))
    assert not r.ok
    assert r.anomaly == "eval stalled"


def test_eval_log_fresh_not_stalled(tmp_path):
    halumem = tmp_path
    official = _mk_official(halumem)
    _write_eval_log(official, "some log content\n", mtime=time.time())
    r = S.check_official_eval(halumem_dir=str(halumem), official_dir=str(official))
    assert r.ok


def test_retry_storm_detected(tmp_path):
    halumem = tmp_path
    official = _mk_official(halumem)
    lines = ["Retrying llms.llm_request_for_json in 2 seconds" for _ in range(60)]
    lines += ["normal progress line" for _ in range(140)]
    _write_eval_log(official, "\n".join(lines), mtime=time.time())
    r = S.check_official_eval(halumem_dir=str(halumem), official_dir=str(official))
    assert not r.ok
    assert r.anomaly == "retry storm (server down?)"


def test_few_retries_not_a_storm(tmp_path):
    halumem = tmp_path
    official = _mk_official(halumem)
    lines = ["Retrying llms.llm_request_for_json in 2 seconds" for _ in range(10)]
    lines += ["normal progress line" for _ in range(190)]
    _write_eval_log(official, "\n".join(lines), mtime=time.time())
    r = S.check_official_eval(halumem_dir=str(halumem), official_dir=str(official))
    assert r.ok


# --------------------------------------------------------------------------
# official eval: checkpoint degeneracy
# --------------------------------------------------------------------------

def test_degenerate_unknown_rate_flagged(tmp_path):
    halumem = tmp_path
    official = _mk_official(halumem)
    _write_eval_log(official, "healthy log\n", mtime=time.time())
    records = [_qa_record(system_response="Unknown.", result_type="Omission")
               for _ in range(163)]
    records += [_qa_record(system_response="Manager", result_type="Correct")]
    _write_checkpoint(official, "user-degenerate", records, mtime=time.time())
    r = S.check_official_eval(halumem_dir=str(halumem), official_dir=str(official))
    assert not r.ok
    assert r.anomaly == "degenerate abstention"


def test_healthy_checkpoint_not_flagged(tmp_path):
    halumem = tmp_path
    official = _mk_official(halumem)
    _write_eval_log(official, "healthy log\n", mtime=time.time())
    _write_checkpoint(official, "user-healthy", _healthy_records(50), mtime=time.time())
    r = S.check_official_eval(halumem_dir=str(halumem), official_dir=str(official))
    assert r.ok
    assert "running" in r.status


def test_hallucination_rate_flagged(tmp_path):
    halumem = tmp_path
    official = _mk_official(halumem)
    _write_eval_log(official, "healthy log\n", mtime=time.time())
    records = [_qa_record(system_response=f"a{i}", result_type="Hallucination")
               for i in range(20)]
    records += [_qa_record(system_response=f"b{i}", result_type="Correct")
                for i in range(80)]
    _write_checkpoint(official, "user-hallu", records, mtime=time.time())
    r = S.check_official_eval(halumem_dir=str(halumem), official_dir=str(official))
    assert not r.ok
    assert r.anomaly == "hallucination rate too high"


def test_none_result_type_rate_flagged(tmp_path):
    halumem = tmp_path
    official = _mk_official(halumem)
    _write_eval_log(official, "healthy log\n", mtime=time.time())
    records = [_qa_record(system_response=f"a{i}", result_type=None)
               for i in range(15)]
    records += [_qa_record(system_response=f"b{i}", result_type="Correct")
                for i in range(85)]
    _write_checkpoint(official, "user-none", records, mtime=time.time())
    r = S.check_official_eval(halumem_dir=str(halumem), official_dir=str(official))
    assert not r.ok
    assert r.anomaly == "result_type None rate too high"


def test_checkpoint_cache_avoids_reparsing(tmp_path):
    halumem = tmp_path
    official = _mk_official(halumem)
    _write_eval_log(official, "healthy log\n", mtime=time.time())
    path = _write_checkpoint(official, "user-cached", _healthy_records(10),
                              mtime=time.time())

    cache = {}
    r1 = S.check_official_eval(halumem_dir=str(halumem), official_dir=str(official),
                                checkpoint_cache=cache)
    assert r1.ok
    assert len(cache) == 1
    key = next(iter(cache))

    # Corrupt the on-disk stats object directly (bypassing re-parse) to
    # prove the cached value -- not a re-read of the file -- is what's used
    # when the file's mtime hasn't changed.
    cache[key] = {"n": 10, "unknown_rate": 0.99, "hallucination_rate": 0.0,
                  "none_rate": 0.0}
    r2 = S.check_official_eval(halumem_dir=str(halumem), official_dir=str(official),
                                checkpoint_cache=cache)
    assert not r2.ok  # served from the (poisoned) cache, not re-parsed from disk
    assert r2.anomaly == "degenerate abstention"

    # But bump mtime -> cache key changes -> re-parsed from the real
    # (healthy) file on disk.
    os.utime(path, (time.time() + 1, time.time() + 1))
    r3 = S.check_official_eval(halumem_dir=str(halumem), official_dir=str(official),
                                checkpoint_cache=cache)
    assert r3.ok
    assert len(cache) == 2


# --------------------------------------------------------------------------
# official eval: fast-finishing users (error-defaulting)
# --------------------------------------------------------------------------

def test_fast_finish_users_flagged(tmp_path):
    halumem = tmp_path
    official = _mk_official(halumem)
    log_lines = []
    # 33s apart, mirroring the real incident.
    base = 8739.62
    for i, uid in enumerate(["u5", "u6", "u7"]):
        log_lines.append(
            f"✅ Finished user {uid} ({i+5}), elapsed {base + i*33:.2f}s."
        )
    _write_eval_log(official, "\n".join(log_lines), mtime=time.time())
    r = S.check_official_eval(halumem_dir=str(halumem), official_dir=str(official))
    assert not r.ok
    assert r.anomaly == "users finishing in minutes (error-defaulting)"


def test_normal_pacing_not_flagged(tmp_path):
    halumem = tmp_path
    official = _mk_official(halumem)
    log_lines = []
    base = 8739.62
    # Real users: thousands of seconds apart.
    for i, uid in enumerate(["u5", "u6", "u7"]):
        log_lines.append(
            f"✅ Finished user {uid} ({i+5}), elapsed {base + i*9000:.2f}s."
        )
    _write_eval_log(official, "\n".join(log_lines), mtime=time.time())
    r = S.check_official_eval(halumem_dir=str(halumem), official_dir=str(official))
    assert r.ok


def test_restart_reset_not_flagged(tmp_path):
    """A script restart resets the cumulative elapsed counter, producing a
    large negative delta -- that's not a fast finish, it's a restart, and
    must not be flagged."""
    halumem = tmp_path
    official = _mk_official(halumem)
    log_lines = [
        "✅ Finished user uA (1), elapsed 39301.97s.",
        "✅ Finished user uB (2), elapsed 18256.80s.",
    ]
    _write_eval_log(official, "\n".join(log_lines), mtime=time.time())
    r = S.check_official_eval(halumem_dir=str(halumem), official_dir=str(official))
    assert r.ok


# --------------------------------------------------------------------------
# process checks
# --------------------------------------------------------------------------

def test_find_running_targets_matches_exact_argv():
    # Our own test process's argv should not spuriously match any target
    # (pytest args don't equal/endswith evaluation.py / dev_set.py /
    # llama_cpp.server).
    found = S.find_running_targets()
    assert found["evaluation.py"] in (True, False)  # just must not raise
    assert isinstance(found, dict)
    assert set(found) == {"evaluation.py", "llama_cpp.server", "dev_set.py"}


def test_find_running_targets_ignores_substring_mentions(tmp_path, monkeypatch):
    """Regression test for the pgrep false-positive incident: a process
    whose command line merely *mentions* the target inside a larger string
    argument (like a pgrep -f pattern) must NOT be detected as the target."""
    fake_proc = tmp_path / "proc"
    fake_pid_dir = fake_proc / "999999"
    fake_pid_dir.mkdir(parents=True)
    # Single argv element containing the substring "dev_set.py" embedded in
    # a much larger string (as a real pgrep -f pattern argument would be).
    cmdline = b"/bin/bash\x00-c\x00" + b"pgrep -f 'dev_set.py extract --users 10-12'\x00"
    (fake_pid_dir / "cmdline").write_bytes(cmdline)

    monkeypatch.setattr(os, "listdir", lambda p: ["999999"] if p == "/proc" else os.listdir(p))

    def fake_read_cmdline(pid):
        path = fake_pid_dir / "cmdline"
        with open(path, "rb") as f:
            raw = f.read()
        return [p for p in raw.split(b"\0") if p]

    monkeypatch.setattr(S, "_read_cmdline", fake_read_cmdline)
    found = S.find_running_targets()
    assert found["dev_set.py"] is False


def test_find_running_targets_matches_real_argv(tmp_path, monkeypatch):
    fake_pid_dir = tmp_path / "9999998"
    fake_pid_dir.mkdir()
    cmdline = b"python3\x00dev_set.py\x00extract\x00--users\x0010-12\x00"
    (fake_pid_dir / "cmdline").write_bytes(cmdline)

    monkeypatch.setattr(os, "listdir", lambda p: ["9999998"] if p == "/proc" else os.listdir(p))

    def fake_read_cmdline(pid):
        with open(fake_pid_dir / "cmdline", "rb") as f:
            raw = f.read()
        return [p for p in raw.split(b"\0") if p]

    monkeypatch.setattr(S, "_read_cmdline", fake_read_cmdline)
    found = S.find_running_targets()
    assert found["dev_set.py"] is True


def test_check_processes_paused_but_running(tmp_path, monkeypatch):
    (tmp_path / ".OFFICIAL_PAUSED").write_text("")
    monkeypatch.setattr(S, "find_running_targets",
                         lambda exclude_pids=None: {"evaluation.py": True,
                                                     "llama_cpp.server": True,
                                                     "dev_set.py": False})
    r = S.check_processes(official_dir=str(tmp_path))
    assert not r.ok
    assert r.anomaly == "paused but running"


def test_check_processes_eval_without_judge(tmp_path, monkeypatch):
    # no pause marker in tmp_path
    monkeypatch.setattr(S, "find_running_targets",
                         lambda exclude_pids=None: {"evaluation.py": True,
                                                     "llama_cpp.server": False,
                                                     "dev_set.py": False})
    r = S.check_processes(official_dir=str(tmp_path))
    assert not r.ok
    assert r.anomaly == "eval without judge server -- will error-default"


def test_check_processes_healthy(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "find_running_targets",
                         lambda exclude_pids=None: {"evaluation.py": True,
                                                     "llama_cpp.server": True,
                                                     "dev_set.py": False})
    r = S.check_processes(official_dir=str(tmp_path))
    assert r.ok


# --------------------------------------------------------------------------
# host checks
# --------------------------------------------------------------------------

def _write_meminfo(tmp_path, mem_avail_kb, swap_total_kb=0, swap_free_kb=0):
    path = tmp_path / "meminfo"
    path.write_text(
        f"MemTotal:       16000000 kB\n"
        f"MemAvailable:   {mem_avail_kb} kB\n"
        f"SwapTotal:      {swap_total_kb} kB\n"
        f"SwapFree:       {swap_free_kb} kB\n"
    )
    return str(path)


def test_ram_crunch_flagged(tmp_path):
    meminfo = _write_meminfo(tmp_path, mem_avail_kb=500_000)  # 0.48 GiB
    r = S.check_host(meminfo_path=meminfo, disk_path=str(tmp_path))
    assert not r.ok
    assert r.anomaly == "RAM crunch"


def test_ram_healthy_not_flagged(tmp_path):
    meminfo = _write_meminfo(tmp_path, mem_avail_kb=12_000_000)  # ~11.4 GiB
    r = S.check_host(meminfo_path=meminfo, disk_path=str(tmp_path))
    assert r.ok


def test_swap_crunch_flagged(tmp_path):
    meminfo = _write_meminfo(
        tmp_path, mem_avail_kb=12_000_000,
        swap_total_kb=4_000_000, swap_free_kb=100_000,  # 97.5% used
    )
    r = S.check_host(meminfo_path=meminfo, disk_path=str(tmp_path))
    assert not r.ok
    assert r.anomaly == "swap crunch"


def test_disk_crunch_flagged(tmp_path, monkeypatch):
    meminfo = _write_meminfo(tmp_path, mem_avail_kb=12_000_000)

    class FakeStatvfs:
        f_bavail = 100
        f_frsize = 1024  # 100 * 1024 bytes ~ tiny, way under 5 GiB

    monkeypatch.setattr(os, "statvfs", lambda path: FakeStatvfs())
    r = S.check_host(meminfo_path=meminfo, disk_path=str(tmp_path))
    assert not r.ok
    assert r.anomaly == "disk crunch"


# --------------------------------------------------------------------------
# dev cache checks
# --------------------------------------------------------------------------

def _write_cache(tmp_path, name, lines, mtime=None):
    path = tmp_path / name
    path.write_text("\n".join(lines) + "\n")
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def test_stale_cache_ignored(tmp_path):
    old = time.time() - 20 * 60  # 20 min ago, outside the 10-min window
    lines = [json.dumps({"h": "x", "f": []}) for _ in range(10)]
    _write_cache(tmp_path, "cache_u1.jsonl", lines, mtime=old)
    r = S.check_dev_caches(dev_dir=str(tmp_path))
    assert r.ok
    assert "no actively-growing" in r.status


def test_active_healthy_cache_not_flagged(tmp_path):
    lines = []
    for i in range(100):
        if i % 3 == 0:
            lines.append(json.dumps({"h": str(i), "f": []}))
        else:
            lines.append(json.dumps({"h": str(i), "f": [{"attribute": "a", "value": "v"}]}))
    _write_cache(tmp_path, "cache_u1.jsonl", lines, mtime=time.time())
    r = S.check_dev_caches(dev_dir=str(tmp_path))
    assert r.ok


def test_cache_corruption_flagged(tmp_path):
    lines = ["{not valid json" for _ in range(50)] + [
        json.dumps({"h": str(i), "f": []}) for i in range(5)
    ]
    _write_cache(tmp_path, "cache_u1.jsonl", lines, mtime=time.time())
    r = S.check_dev_caches(dev_dir=str(tmp_path))
    assert not r.ok
    assert r.anomaly == "cache corruption"


def test_degenerate_extraction_flagged(tmp_path):
    lines = [json.dumps({"h": str(i), "f": []}) for i in range(100)]
    _write_cache(tmp_path, "cache_u1.jsonl", lines, mtime=time.time())
    r = S.check_dev_caches(dev_dir=str(tmp_path))
    assert not r.ok
    assert r.anomaly == "degenerate extraction"


# --------------------------------------------------------------------------
# run_checks: isolation between checks
# --------------------------------------------------------------------------

def test_run_checks_survives_broken_checkpoint(tmp_path):
    halumem = tmp_path
    official = _mk_official(halumem)
    _write_eval_log(official, "healthy log\n", mtime=time.time())
    # Malformed JSON checkpoint -- must not crash the sentinel.
    bad_path = (
        official / "HaluMem" / "eval" / "results" / "rgp2-default" / "tmp2"
        / "bad.json"
    )
    bad_path.write_text("{not json")

    paths = S.SentinelPaths(halumem_dir=str(halumem), official_dir=str(official),
                             dev_dir=str(tmp_path / "dev"), disk_path=str(tmp_path))
    results = S.run_checks(paths)
    names = {r.name for r in results}
    assert "official_eval" in names
    official_result = next(r for r in results if r.name == "official_eval")
    assert official_result.status == "check errored"
    # Other checks still ran.
    assert "host" in names
    assert "processes" in names
    assert "dev_caches" in names


def test_run_checks_healthy_path(tmp_path):
    halumem = tmp_path
    official = _mk_official(halumem)
    _write_eval_log(official, "healthy log\n", mtime=time.time())
    _write_checkpoint(official, "user-ok", _healthy_records(20), mtime=time.time())
    dev_dir = tmp_path / "dev"
    dev_dir.mkdir()
    meminfo = _write_meminfo(tmp_path, mem_avail_kb=12_000_000)

    paths = S.SentinelPaths(halumem_dir=str(halumem), official_dir=str(official),
                             dev_dir=str(dev_dir), meminfo_path=meminfo,
                             disk_path=str(tmp_path))
    results = S.run_checks(paths)
    assert all(r.ok for r in results), [r.line() for r in results]


def test_print_report_and_exit_code(tmp_path, capsys, monkeypatch):
    halumem = tmp_path
    official = _mk_official(halumem)
    (official / ".OFFICIAL_PAUSED").write_text("")
    dev_dir = tmp_path / "dev"
    dev_dir.mkdir()
    # hermetic: the REAL host may legitimately be running evaluation.py while
    # this fixture plants a paused marker -- the process check would then
    # (correctly) flag "paused but running" and fail this exit-code test for
    # environmental reasons. Stub the process scan to an idle host.
    monkeypatch.setattr(S, "find_running_targets",
                        lambda exclude_pids=None: {"evaluation.py": False,
                                                    "llama_cpp.server": False,
                                                    "dev_set.py": False})
    paths = S.SentinelPaths(halumem_dir=str(halumem), official_dir=str(official),
                             dev_dir=str(dev_dir), disk_path=str(tmp_path))
    code = S.cmd_report(paths)
    captured = capsys.readouterr()
    assert "sentinel report" in captured.out
    assert code == 0
