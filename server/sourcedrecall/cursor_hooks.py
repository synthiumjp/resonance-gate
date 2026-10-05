"""Automatic memory for Cursor's agent: one hook command for several events.

    sourcedrecall-hook cursor --owner "Your Name"

in ~/.cursor/hooks.json (or <project>/.cursor/hooks.json), for the events
beforeSubmitPrompt, afterAgentResponse, stop, sessionStart and sessionEnd.
The command reads the event from stdin and tells them apart by its
"hook_event_name" field.

2026-10-05. What Cursor documents (https://cursor.com/docs/hooks, the
Reference section; read as markdown from https://cursor.com/docs/hooks.md):

  * every event carries "conversation_id" (stable across the turns of one
    conversation), "workspace_roots", "hook_event_name" and
    "transcript_path" (a path, or null when transcripts are off);
  * beforeSubmitPrompt adds "prompt", the text the user typed, and expects
    {"continue": true|false} back;
  * afterAgentResponse adds "text", the assistant's message;
  * stop adds "status" (completed, aborted, error) and fires when the agent
    loop ends;
  * sessionStart adds "session_id" (same as conversation_id) and accepts
    {"additional_context": "..."} back;
  * sessionEnd adds "session_id" and "reason", fire-and-forget.

Cursor does NOT document the format of the transcript file, nor where it
keeps chat history, so this module never reads either. It records the
documented prompt and response texts itself, one JSON line each, in
$SOURCEDRECALL_STATE/cursor-spool/<conversation_id>.jsonl, and stores that
at each stop and at sessionEnd (then deletes the spool). Storing is safe to
repeat: only turns not already stored are added.

Limits that follow from the documentation:
  * only what passes through those two hooks is seen. Text in a turn that
    ran before the hooks were installed is not;
  * sessionStart is fire-and-forget, and its output has no field that shows
    a message to the user, so the "saved N new things" line that Claude
    Code users see is not available here;
  * hooks in ~/.cursor/hooks.json do not run in Cursor's cloud agents
    (project hooks do, but sessionStart and sessionEnd do not).
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

_KEEP_DAYS = 30


def _spool_dir():
    from sourcedrecall.paths import state_dir
    d = os.path.join(state_dir(), "cursor-spool")
    os.makedirs(d, exist_ok=True)
    return d


def spool_path(conversation_id):
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", str(conversation_id))[:120]
    return os.path.join(_spool_dir(), safe + ".jsonl")


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _append(conversation_id, role, text, cwd=None):
    text = (text or "").strip()
    if not text:
        return
    rec = {"role": role, "content": text, "ts": _now()}
    if cwd:
        rec["cwd"] = cwd
    with open(spool_path(conversation_id), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def _forget_old_spools():
    d = _spool_dir()
    cutoff = time.time() - _KEEP_DAYS * 86400
    for name in os.listdir(d):
        p = os.path.join(d, name)
        try:
            if name.endswith(".jsonl") and os.path.getmtime(p) < cutoff:
                os.unlink(p)
        except OSError:
            pass


def read_spool(path):
    """-> (turns, first_timestamp, cwd). Consecutive assistant messages
    (the agent often speaks between tool calls) become one turn."""
    turns, first_ts, cwd = [], None, None
    try:
        fh = open(path, encoding="utf-8")
    except OSError:
        return turns, first_ts, cwd
    with fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            role, text = r.get("role"), r.get("content")
            if role not in ("user", "assistant") or not isinstance(text, str):
                continue
            first_ts = first_ts or r.get("ts")
            cwd = r.get("cwd") or cwd
            if role == "assistant" and turns and turns[-1]["role"] == "assistant":
                turns[-1]["content"] += "\n" + text
            else:
                turns.append({"role": role, "content": text})
    return turns, first_ts, cwd


def ingest_spool(path, conversation_id, owner=None, cwd=None, delete=False):
    """The worker: store what the spool holds; optionally remove it."""
    from sourcedrecall import claude_hooks
    turns, first_ts, spool_cwd = read_spool(path)
    out = claude_hooks.ingest_turns(turns, f"cursor:{conversation_id}", first_ts,
                                    owner, cwd or spool_cwd)
    if delete:
        try:
            os.unlink(path)
        except OSError:
            pass
    return out


def _store(conversation_id, owner, cwd, delete, sync):
    path = spool_path(conversation_id)
    if not os.path.exists(path):
        return {"stored": False, "reason": "nothing recorded for this conversation"}
    if sync:
        return ingest_spool(path, conversation_id, owner, cwd, delete)
    # Loading the parser takes seconds; hand the work to a detached process
    # and return at once, as the Claude Code session-end hook does.
    job = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                      prefix="sourcedrecall-job-")
    json.dump({"spool": path, "conversation_id": conversation_id, "owner": owner,
               "cwd": cwd, "delete": delete}, job)
    job.close()
    log = os.path.join(tempfile.gettempdir(), "sourcedrecall-hook.log")
    with open(log, "a") as lf:
        subprocess.Popen([sys.executable, "-m", "sourcedrecall.claude_hooks",
                          "_worker", job.name],
                         stdin=subprocess.DEVNULL, stdout=lf, stderr=lf,
                         start_new_session=True)
    return {"stored": "pending", "job": job.name, "log": log}


def _reply(name):
    # beforeSubmitPrompt must answer {"continue": true} or the prompt is
    # not sent; every other event ignores the reply.
    return {"continue": True} if name == "beforeSubmitPrompt" else {}


def handle(event, owner=None, sync=False):
    """Handle one Cursor hook event and return the JSON to print. Never
    raises and never blocks the user's prompt: a failure here is logged to
    stderr and the reply is the harmless one."""
    name = event.get("hook_event_name")
    try:
        conv = event.get("conversation_id") or event.get("session_id")
        roots = event.get("workspace_roots") or []
        cwd = roots[0] if roots and isinstance(roots[0], str) else None
        if not conv:
            return _reply(name)
        if name == "beforeSubmitPrompt":
            _append(conv, "user", event.get("prompt"), cwd)
            _forget_old_spools()
        elif name == "afterAgentResponse":
            _append(conv, "assistant", event.get("text"))
        elif name == "stop":
            _store(conv, owner, cwd, False, sync)
        elif name == "sessionEnd":
            _store(conv, owner, cwd, True, sync)
        elif name == "sessionStart":
            from sourcedrecall import claude_hooks
            out = claude_hooks.session_start({"cwd": cwd}, owner, agent="cursor",
                                             show_notice=False)
            ctx = ((out or {}).get("hookSpecificOutput") or {}).get("additionalContext")
            return {"additional_context": ctx} if ctx else {}
    except Exception as e:                      # noqa: BLE001
        print(f"sourcedrecall cursor hook ({name}): {e!r}", file=sys.stderr)
    return _reply(name)
