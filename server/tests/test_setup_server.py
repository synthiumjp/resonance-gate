"""The plugin's stand-in MCP server (plugins/sourcedrecall/bin/setup_server.py):
answers while the install runs, then hands over to the real server in the
same session (2026-10-14; JP's first session had no memory tools)."""
import json
import os
import queue
import subprocess
import sys
import threading
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STUB = os.path.join(ROOT, "plugins", "sourcedrecall", "bin", "setup_server.py")

FAKE_SERVER = r'''
import json, sys
for line in sys.stdin:
    m = json.loads(line)
    if m.get("method") == "initialize":
        r = {"protocolVersion": m["params"]["protocolVersion"], "capabilities": {"tools": {}},
             "serverInfo": {"name": "real", "version": "1"}}
    elif m.get("method") == "tools/list":
        r = {"tools": [{"name": "memory_recall", "inputSchema": {"type": "object"}}]}
    elif m.get("method") == "quit":
        sys.exit(3)
    elif "id" in m:
        r = {"echo": m.get("method")}
    else:
        continue
    print(json.dumps({"jsonrpc": "2.0", "id": m["id"], "result": r}), flush=True)
'''


class Stub:
    def __init__(self, tmp_path):
        self.d = tmp_path
        exe = tmp_path / "sourcedrecall"
        exe.write_text(f"#!{sys.executable}\n{FAKE_SERVER}")
        exe.chmod(0o755)
        self.stamp = tmp_path / "installed"
        (tmp_path / "install.log").write_text("[2/4] retrieval embedder\n")
        env = dict(os.environ, SOURCEDRECALL_SETUP_POLL="0.1")
        self.p = subprocess.Popen(
            [sys.executable, STUB, str(exe), str(self.stamp), "v1", str(tmp_path / "install.log"),
             str(tmp_path / "install.failed"), str(tmp_path / "install.lock")],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env=env)
        self.out = queue.Queue()
        threading.Thread(target=lambda: [self.out.put(json.loads(l)) for l in self.p.stdout],
                         daemon=True).start()
        self.n = 0

    def send(self, method, params=None, notify=False):
        m = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        if not notify:
            self.n += 1
            m["id"] = self.n
        self.p.stdin.write(json.dumps(m) + "\n")
        self.p.stdin.flush()
        return None if notify else self.n

    def get(self, timeout=10):
        return self.out.get(timeout=timeout)

    def call(self, method, params=None):
        i = self.send(method, params)
        while True:
            m = self.get()
            if m.get("id") == i:
                return m

    def close(self):
        if self.p.poll() is None:
            self.p.kill()
        self.p.wait()


@pytest.fixture
def stub(tmp_path):
    s = Stub(tmp_path)
    yield s
    s.close()


def _init(s):
    r = s.call("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                              "clientInfo": {"name": "t", "version": "0"}})
    s.send("notifications/initialized", notify=True)
    return r


def test_answers_during_setup_then_hands_over(stub):
    r = _init(stub)
    assert r["result"]["capabilities"]["tools"]["listChanged"] is True
    assert r["result"]["protocolVersion"] == "2025-06-18"
    tools = stub.call("tools/list")["result"]["tools"]
    assert [t["name"] for t in tools] == ["memory_setup_status"]
    text = stub.call("tools/call", {"name": "memory_setup_status", "arguments": {}})
    assert "still setting up" in text["result"]["content"][0]["text"]
    assert "retrieval embedder" in text["result"]["content"][0]["text"]
    assert stub.call("ping")["result"] == {}

    stub.stamp.write_text("v1\n")                 # the install finishes
    assert stub.get() == {"jsonrpc": "2.0", "method": "notifications/tools/list_changed"}
    tools = stub.call("tools/list")["result"]["tools"]
    assert [t["name"] for t in tools] == ["memory_recall"]
    assert stub.call("resources/list")["result"] == {"echo": "resources/list"}


def test_wrong_version_stamp_is_not_installed(stub):
    _init(stub)
    stub.stamp.write_text("v0\n")
    time.sleep(0.5)
    assert stub.call("tools/list")["result"]["tools"][0]["name"] == "memory_setup_status"


def test_reports_a_failed_install(stub):
    _init(stub)
    (stub.d / "install.log").write_text("pip: no space left on device\n")
    (stub.d / "install.failed").write_text("x")
    r = stub.call("tools/call", {"name": "memory_setup_status", "arguments": {}})["result"]
    assert r["isError"] is True
    assert "install failed" in r["content"][0]["text"]
    assert "no space left" in r["content"][0]["text"]


def test_unknown_request_during_setup_is_an_error_not_silence(stub):
    _init(stub)
    r = stub.call("resources/read", {"uri": "x"})
    assert r["error"]["code"] == -32601


def test_exits_with_the_real_server(stub):
    _init(stub)
    stub.stamp.write_text("v1\n")
    stub.get()                                     # list_changed
    stub.send("quit")
    assert stub.p.wait(timeout=10) == 3


def test_closing_stdin_before_install_exits_cleanly(stub):
    _init(stub)
    stub.p.stdin.close()
    assert stub.p.wait(timeout=10) == 0
