#!/usr/bin/env bash
# Clean-install test (launch gate 1, 2026-10-13): a new user with an empty
# home installs the Claude Code plugin through its own launcher, from a git
# URL at a ref, then two sessions go through the real hooks, then the
# briefing a third session gets and the memory CLI are checked. Exits
# non-zero if any step fails or the memory is wrong.
#
#   tools/clean_install_test.sh REPO_URL REF [WORK_DIR]
#   e.g. tools/clean_install_test.sh file://$PWD v-test /tmp/sdr-clean
#
# Needs git, Python 3.10-3.13 and the network (models from Hugging Face).
set -u
REPO_URL=$1; REF=$2; C=${3:-${TMPDIR:-/tmp}/sourcedrecall-clean-test}
rm -rf "$C"; mkdir -p "$C/home"
git clone -q "$REPO_URL" "$C/checkout" && git -C "$C/checkout" checkout -q "$REF" || exit 1
cp -R "$C/checkout/plugins/sourcedrecall" "$C/plugin"
REAL_HOME=$HOME
export HOME="$C/home" USERPROFILE="$C/home"   # Python reads USERPROFILE on Windows
export CLAUDE_PLUGIN_ROOT="$C/plugin" CLAUDE_PLUGIN_DATA="$HOME/.claude/plugins/data/sourcedrecall"
export SOURCEDRECALL_REPO_URL="$REPO_URL" SOURCEDRECALL_REF="$REF" SOURCEDRECALL_OWNER="Dana Cole"
R="$CLAUDE_PLUGIN_ROOT/bin/sourcedrecall-run"
fail() {
  echo "FAIL: $*"
  echo "-- diagnostics"; ls -laR "$HOME/.sourcedrecall" 2>/dev/null | head -40
  tail -40 "$HOME/.sourcedrecall/hook.log" 2>/dev/null
  [ -n "${PY:-}" ] && "$(dirname "$PY")/sourcedrecall-memory" status
  exit 1; }
t0=$(date +%s)

echo "== 1. first session start, before anything is installed"
out=$(echo '{"session_id":"s0","hook_event_name":"SessionStart","source":"startup","transcript_path":null}' | bash "$R" hook session-start)
echo "$out" | grep -q "setting up local memory" || fail "no first-run message: $out"
for i in $(seq 1 120); do [ -d "$CLAUDE_PLUGIN_DATA/install.lock" ] || break; sleep 5; done   # the background install

echo "== 2. install"
bash "$R" install || { tail -20 "$CLAUDE_PLUGIN_DATA/install.log"; fail "install"; }
echo "install done after $(( $(date +%s) - t0 )) s"
du -sh "$HOME/.sourcedrecall" "$CLAUDE_PLUGIN_DATA" 2>/dev/null

PY=$(ls "$CLAUDE_PLUGIN_DATA"/venv/bin/python* "$CLAUDE_PLUGIN_DATA"/venv/Scripts/python.exe 2>/dev/null | head -1)
mk() {  # file date user assistant [user assistant ...]
  local f=$1 d=$2; shift 2
  "$PY" - "$f" "$d" "$@" <<'EOF'
import json, sys
f, d, turns = sys.argv[1], sys.argv[2], sys.argv[3:]
with open(f, "w", encoding="utf-8") as out:
    for k, text in enumerate(turns):
        role = "user" if k % 2 == 0 else "assistant"
        content = text if role == "user" else [{"type": "text", "text": text}]
        out.write(json.dumps({"type": role, "timestamp": f"{d}T09:00:0{k % 10}Z",
                              "message": {"role": role, "content": content}}) + "\n")
EOF
}
mk "$C/s1.jsonl" 2026-09-25 "I work as a nurse at St Vincent's and I live in Fitzroy." "Got it." \
   "can you help me reply to this one from Marcus? Hi Dana, Thanks for the invite to Saturday's dinner, count me in. Just so you know, I'm allergic to nuts and I don't drink alcohol. Best, Marcus" "Sure, here's a draft."
mk "$C/s2.jsonl" 2026-10-02 "Big news, I moved to Brunswick last weekend." "Congratulations!"
for s in s1 s2; do
  echo "== 3. session end $s"
  # JSON-encoded, as Claude Code sends it (a Windows path has backslashes)
  "$PY" -c "import json, sys; print(json.dumps({'session_id': sys.argv[1], 'hook_event_name': 'SessionEnd', 'reason': 'exit', 'transcript_path': sys.argv[2]}))" "$s" "$C/$s.jsonl" \
    | bash "$R" hook session-end || fail "session end $s"
done
echo "== 4. waiting for the background workers (until the briefing has the second session)"
brief_now() { echo '{"session_id":"s3","hook_event_name":"SessionStart","source":"startup","transcript_path":null}' | bash "$R" hook session-start; }
for i in $(seq 1 36); do brief_now | grep -q "Brunswick" && break; sleep 5; done
echo "waited ~$((i * 5)) s"

echo "== 5. next session start: the briefing"
brief=$(echo '{"session_id":"s3","hook_event_name":"SessionStart","source":"startup","transcript_path":null}' | bash "$R" hook session-start)
echo "$brief" | cut -c1-600
echo "$brief" | grep -q "Brunswick" || fail "the briefing does not have the move"
echo "$brief" | grep -qi "allergic" && fail "the briefing gives Marcus's allergy as the user's"

echo "== 6. CLI"
V=$(dirname "$PY")
ctx=$("$V/sourcedrecall-memory" context "Where do I live?") || fail "context"
echo "$ctx" | head -5
echo "$ctx" | grep -q "no longer true" || fail "Fitzroy is not marked out of date"
ctx=$("$V/sourcedrecall-memory" context "What am I allergic to?") || fail "context"
echo "$ctx" | grep -q "pasted in by" || fail "Marcus's email is not marked as pasted"
"$V/sourcedrecall-memory" status || fail "status"
grep -qi "allergic" "$HOME/.sourcedrecall/MEMORY.md" "$HOME"/.sourcedrecall/*/MEMORY.md 2>/dev/null && fail "MEMORY.md gives the allergy as the user's"
echo "== 7. MCP server: initialize, tools/list, profile_context"
cat > "$C/mcp_check.py" <<'EOF'
"""Talk to an MCP stdio server: initialize, tools/list, profile_context.
usage: mcp_check.py LABEL COMMAND [ARGS...]"""
import json, queue, subprocess, sys, threading
label, cmd = sys.argv[1], sys.argv[2:]
p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
q = queue.Queue()
threading.Thread(target=lambda: [q.put(l) for l in iter(p.stdout.readline, b"")] + [q.put(None)], daemon=True).start()
def stop(why):
    p.kill()
    sys.exit(f"{label}: {why}; stderr: {p.stderr.read().decode('utf-8', 'replace')[-600:]!r}")
def send(m):
    p.stdin.write((json.dumps(m) + "\n").encode()); p.stdin.flush()
def reply(i, wait=120):
    while True:
        try:
            line = q.get(timeout=wait)
        except queue.Empty:
            stop(f"no reply to request {i} in {wait} s")
        if line is None:
            stop("the server closed")
        try:
            m = json.loads(line)
        except ValueError:
            stop(f"not JSON on stdout: {line[:200]!r}")
        if m.get("id") == i:
            return m
send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
    "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "clean-install-test", "version": "0"}}})
print(label, "server:", reply(1)["result"]["serverInfo"])
send({"jsonrpc": "2.0", "method": "notifications/initialized"})
send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
tools = [t["name"] for t in reply(2)["result"]["tools"]]
assert "profile_context" in tools and "profile_ingest" in tools, tools
send({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
      "params": {"name": "profile_context", "arguments": {"query": "Where do I live?"}}})
text = json.dumps(reply(3)["result"])
assert "Brunswick" in text and "no longer true" in text, text[:800]
print(label, "ok:", len(tools), "tools; profile_context gives Brunswick, Fitzroy out of date")
p.kill()
EOF
SERVER=$(ls "$(dirname "$PY")"/sourcedrecall.exe "$(dirname "$PY")"/sourcedrecall 2>/dev/null | head -1)
"$PY" "$C/mcp_check.py" "direct" "$SERVER" || fail "MCP server started directly"
# through the plugin launcher, with the bash running this test (on Windows,
# plain "bash" can be the WSL launcher); how Claude Code itself starts it on
# native Windows is not documented
BASH_EXE=$(command -v cygpath >/dev/null 2>&1 && cygpath -w "$BASH" || echo "$BASH")
"$PY" "$C/mcp_check.py" "launcher" "$BASH_EXE" "$R" mcp || fail "MCP server through the launcher"
HOME=$REAL_HOME
echo "== passed after $(( $(date +%s) - t0 )) s"
