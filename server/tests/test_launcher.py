"""The plugin launcher (plugins/sourcedrecall/bin/sourcedrecall-run), run
with a stub environment: nothing is installed or downloaded.

2026-10-21 (review): a plugin user was told to run commands that are not on
their PATH; Claude Code's shell has no CLAUDE_PLUGIN_DATA, so the launcher
could not find the plugin's environment from there; a failed install stayed
failed for good."""
import os
import shutil
import subprocess
import sys
import time

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "plugins", "sourcedrecall")
RUN = os.path.join(ROOT, "bin", "sourcedrecall-run")

pytestmark = pytest.mark.skipif(sys.platform == "win32" or not shutil.which("bash"),
                                reason="the launcher is a bash script")


def _ref():
    import json
    with open(os.path.join(ROOT, ".claude-plugin", "plugin.json")) as f:
        return "sourcedrecall-v" + json.load(f)["version"]


def _run(args, tmp_path, data=True, **env):
    e = {k: v for k, v in os.environ.items()
         if not k.startswith(("CLAUDE_PLUGIN", "SOURCEDRECALL_"))}
    e.update(HOME=str(tmp_path / "home"), SOURCEDRECALL_STATE=str(tmp_path / "state"),
             CLAUDE_PLUGIN_ROOT=ROOT, **env)
    if data:
        e["CLAUDE_PLUGIN_DATA"] = str(tmp_path / "data")
    return subprocess.run(["bash", RUN, *args], env=e, capture_output=True, text=True,
                          timeout=60)


def _stub_install(tmp_path):
    vbin = tmp_path / "data" / "venv" / "bin"
    vbin.mkdir(parents=True)
    for name in ("sourcedrecall-memory", "sourcedrecall-import"):
        p = vbin / name
        p.write_text(f"#!/bin/sh\necho {name} \"$@\"\n")
        p.chmod(0o755)


def test_memory_commands_reach_the_plugin_environment_from_claude_codes_shell(tmp_path):
    _stub_install(tmp_path)
    # a hook run (CLAUDE_PLUGIN_DATA set) records where the plugin lives ...
    assert _run(["memory", "status"], tmp_path).returncode == 0
    assert (tmp_path / "state" / "plugin-data").read_text().strip() == str(tmp_path / "data")
    # ... so a run from Claude Code's shell, without it, finds the same place
    out = _run(["memory", "forget", "ab12cd"], tmp_path, data=False)
    assert out.returncode == 0 and out.stdout.strip() == "sourcedrecall-memory forget ab12cd"
    assert _run(["import", "chatgpt", "x.zip"], tmp_path, data=False).stdout.strip() == \
        "sourcedrecall-import chatgpt x.zip"


def test_a_memory_command_before_the_install_says_so(tmp_path):
    out = _run(["memory", "show"], tmp_path)
    assert out.returncode == 1 and "not installed yet" in out.stderr


def test_a_failed_install_is_retried_after_an_hour_or_for_another_version(tmp_path):
    _stub_install(tmp_path)
    failed = tmp_path / "data" / "install.failed"
    failed.write_text(f"{_ref()}\nyesterday\n")
    _run(["memory", "status"], tmp_path)
    assert failed.exists()                       # this version, just now: kept
    old = time.time() - 2 * 3600
    os.utime(failed, (old, old))
    _run(["memory", "status"], tmp_path)
    assert not failed.exists()                   # an hour later: tried again
    failed.write_text("sourcedrecall-v0.0.1\nyesterday\n")
    _run(["memory", "status"], tmp_path)
    assert not failed.exists()                   # another version: tried again


def test_messages_name_the_command_the_user_can_run(monkeypatch):
    from sourcedrecall.paths import command
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", ROOT)
    assert command("memory show") == "! sourcedrecall-run memory show"
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT")
    assert command("memory show") == "sourcedrecall-memory show"
