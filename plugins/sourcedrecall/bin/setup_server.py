"""Stand-in MCP server while sourcedrecall installs (2026-10-14).

Claude Code starts the MCP server when a session opens. The first time,
the Python side is still installing; the launcher used to exit, Claude Code
cached the failure, and the memory tools were missing for the whole session
even after the install had finished (JP's first session: install done at
09:07:09, the server tried at 09:05:40 and never again).

This server answers at once with one tool, memory_setup_status. When the
install finishes it starts the real server, replays the client's initialize
to it, and from then on passes every message through unchanged, telling the
client that the tool list has changed. Standard library only: it runs on the
system Python, before the venv exists.

    python3 setup_server.py SERVER_EXE STAMP REF LOG FAILED_FLAG LOCK_DIR
"""
import json
import os
import queue
import subprocess
import sys
import threading

EXE, STAMP, REF, LOG, FAILED, LOCK = sys.argv[1:7]
POLL = float(os.environ.get("SOURCEDRECALL_SETUP_POLL", "2"))

out_lock = threading.Lock()


def send(msg):
    line = json.dumps(msg) if isinstance(msg, dict) else msg
    with out_lock:
        sys.stdout.write(line.rstrip("\n") + "\n")
        sys.stdout.flush()


def installed():
    try:
        with open(STAMP) as f:
            return f.read().strip() == REF and os.access(EXE, os.X_OK)
    except OSError:
        return False


def failed():
    return os.path.exists(FAILED) and not os.path.isdir(LOCK)


def progress():
    try:
        with open(LOG, errors="replace") as f:
            lines = [l.strip() for l in f.read().splitlines() if l.strip()]
    except OSError:
        lines = []
    if failed():
        tail = "\n".join(lines[-8:])
        return ("sourcedrecall: the install failed. The reason is at the end of "
                f"{LOG}:\n{tail}")
    last = lines[-1] if lines else "starting"
    return ("sourcedrecall is still setting up (the first time only, usually a few "
            f"minutes). The memory tools appear here when it is done. Last step: {last}")


TOOL = {
    "name": "memory_setup_status",
    "description": ("sourcedrecall is installing its local models (first run only). "
                    "Call this to see how far the install has got; the memory tools "
                    "replace it when the install finishes."),
    "inputSchema": {"type": "object", "properties": {}},
}


def answer(msg, init):
    """Reply to one client message while the real server is not running yet."""
    method, mid = msg.get("method"), msg.get("id")
    if method == "initialize":
        init["request"] = msg
        version = (msg.get("params") or {}).get("protocolVersion", "2025-06-18")
        send({"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersion": version,
            "capabilities": {"tools": {"listChanged": True}},
            "serverInfo": {"name": "sourcedrecall", "version": REF},
            "instructions": "sourcedrecall is installing (first run). Memory tools appear when it finishes.",
        }})
    elif method == "notifications/initialized":
        init["initialized"] = msg
    elif mid is None:
        pass                                   # other notifications
    elif method == "ping":
        send({"jsonrpc": "2.0", "id": mid, "result": {}})
    elif method == "tools/list":
        send({"jsonrpc": "2.0", "id": mid, "result": {"tools": [TOOL]}})
    elif method == "tools/call":
        send({"jsonrpc": "2.0", "id": mid, "result": {
            "content": [{"type": "text", "text": progress()}],
            "isError": failed()}})
    elif method in ("resources/list", "prompts/list"):
        key = method.split("/")[0]
        send({"jsonrpc": "2.0", "id": mid, "result": {key: []}})
    else:
        send({"jsonrpc": "2.0", "id": mid,
              "error": {"code": -32601, "message": f"{method}: sourcedrecall is still setting up"}})


def start_real(init):
    """Start the real server and replay the handshake; None if it fails."""
    try:
        child = subprocess.Popen([EXE], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 text=True, encoding="utf-8", bufsize=1)
    except OSError as e:
        sys.stderr.write(f"sourcedrecall: could not start {EXE}: {e}\n")
        return None
    req = dict(init["request"], id="sourcedrecall-setup-init")
    child.stdin.write(json.dumps(req) + "\n")
    child.stdin.flush()
    for line in child.stdout:                  # until the reply to our initialize
        try:
            if json.loads(line).get("id") == req["id"]:
                break
        except ValueError:
            continue
    else:
        sys.stderr.write("sourcedrecall: the server closed during start-up\n")
        return None
    child.stdin.write(json.dumps(init.get("initialized")
                                 or {"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
    child.stdin.flush()
    return child


def main():
    inbox = queue.Queue()

    def read_stdin():
        for line in sys.stdin:
            if line.strip():
                inbox.put(line)
        inbox.put(None)

    threading.Thread(target=read_stdin, daemon=True).start()
    init = {}
    tries = 0
    while True:                                # stand-in until installed
        try:
            line = inbox.get(timeout=POLL)
        except queue.Empty:
            line = ""
        if line is None:
            return 0
        if line:
            try:
                answer(json.loads(line), init)
            except ValueError:
                pass
        if "request" in init and tries < 3 and installed():
            tries += 1
            child = start_real(init)
            if child is not None:
                break

    def pump():                                # the server's replies, as they are
        for out in child.stdout:
            send(out)
        os._exit(child.wait())                 # the server stopped: so do we
    t = threading.Thread(target=pump, daemon=True)
    t.start()
    send({"jsonrpc": "2.0", "method": "notifications/tools/list_changed"})
    while True:                                # pass-through
        line = inbox.get()
        if line is None:
            break
        try:
            child.stdin.write(line)
            child.stdin.flush()
        except (BrokenPipeError, OSError):
            break
    try:
        child.stdin.close()
    except OSError:
        pass
    rc = child.wait()
    t.join(timeout=5)
    return rc


if __name__ == "__main__":
    sys.exit(main())
