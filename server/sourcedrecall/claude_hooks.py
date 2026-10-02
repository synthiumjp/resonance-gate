"""Automatic memory for Claude Code: two hooks.

    sourcedrecall-hook session-end   --owner "Your Name"   (SessionEnd)
    sourcedrecall-hook session-start --owner "Your Name"   (SessionStart)

session-end reads the finished session's transcript and stores it with
profile_ingest -- the user's own words become facts, receipted, exactly as
if the agent had called the tool. session-start prints the memory briefing
(profile_context) as additional context, so the agent starts every session
knowing what the user has told it before.

2026-10-02. Written because the second new-user test found the product's
biggest remaining gap: nothing captured conversations, so the agent had to
remember to call profile_ingest, and mostly would not.

Two constraints from the Claude Code hooks reference shaped this:
  * SessionEnd hooks share a 1.5 s budget by default and cannot block, and
    loading the parser takes several seconds. So session-end only reads the
    transcript, writes a job file and starts a DETACHED worker, then returns.
  * The transcript format is not a documented contract. The reader below
    keeps exactly two things -- what the human typed and the assistant's
    visible text -- and skips everything else (tool calls, tool results,
    thinking, meta and sidechain lines, slash-command echoes), so an unknown
    new line type is ignored rather than stored.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

# User-typed strings that are not the user talking: slash-command echoes,
# local command output, the harness's own injected caveats.
_NOT_SPEECH = re.compile(
    r"^\s*(<command-name>|<command-message>|<command-args>|<local-command-"
    r"|<bash-input>|<bash-stdout>|<bash-stderr>|Caveat:)", re.S)
_INJECTED = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)
_OWN_SUMMARY = re.compile(r"\[MEMORY[^\]]*\].*?(?:\[MEMORY RULES\][^\n]*|\Z)", re.S)


def _text_items(content):
    if isinstance(content, str):
        return [content]
    out = []
    for it in content or []:
        if isinstance(it, dict) and it.get("type") == "text":
            out.append(it.get("text") or "")
    return out


def read_transcript(path):
    """-> (turns, first_timestamp). turns: [{"role", "content"}], oldest
    first, consecutive assistant chunks merged into one turn."""
    turns, first_ts = [], None
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                o = json.loads(line)
            except ValueError:
                continue
            if o.get("isSidechain") or o.get("isMeta"):
                continue
            t = o.get("type")
            if t not in ("user", "assistant"):
                continue
            msg = o.get("message") or {}
            content = msg.get("content")
            if t == "user":
                if isinstance(content, list) and any(
                        isinstance(it, dict) and it.get("type") == "tool_result"
                        for it in content):
                    continue                      # tool output, not the human
                text = "\n".join(_text_items(content))
                text = _INJECTED.sub("", text).strip()
                # our own summary, if it is ever recorded as user text, must
                # not be stored again -- a memory that re-reads what it
                # recalled grows copies of its own output (a Mem0 audit,
                # issue #4573, found 668 copies of one hallucination)
                text = _OWN_SUMMARY.sub("", text).strip()
                if not text or _NOT_SPEECH.match(text):
                    continue
                role = "user"
            else:
                text = "\n".join(_text_items(content)).strip()
                if not text:
                    continue                      # thinking / tool_use only
                role = "assistant"
            if first_ts is None and o.get("timestamp"):
                first_ts = o["timestamp"]
            if role == "assistant" and turns and turns[-1]["role"] == "assistant":
                turns[-1]["content"] += "\n" + text
            else:
                turns.append({"role": role, "content": text})
    return turns, first_ts


def _setup_env(owner):
    if owner:
        os.environ["SOURCEDRECALL_OWNER"] = owner
    from sourcedrecall.paths import default_memory_dir
    default_memory_dir()
    from sourcedrecall import profile_memory
    return profile_memory


def ingest_session(transcript_path, session_id, owner=None):
    """The worker: store one session. Safe to repeat -- a resumed session
    re-sends its whole transcript and only new turns are added."""
    turns, first_ts = read_transcript(transcript_path)
    if not any(t["role"] == "user" for t in turns):
        return {"stored": False, "reason": "no user speech in this session"}
    pm = _setup_env(owner)
    title = next(t["content"] for t in turns if t["role"] == "user")
    title = " ".join(title.split())[:60]
    return pm.profile_ingest(turns, conversation_id=f"claude-code:{session_id}",
                             title=title,
                             owner_name=os.environ.get("SOURCEDRECALL_OWNER"),
                             date=first_ts)


def session_end(event, owner=None, sync=False):
    path, sid = event.get("transcript_path"), event.get("session_id")
    if not path or not sid or not os.path.exists(path):
        return {"stored": False, "reason": "no transcript"}
    if sync:
        return ingest_session(path, sid, owner)
    job = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                      prefix="sourcedrecall-job-")
    json.dump({"transcript_path": path, "session_id": sid, "owner": owner}, job)
    job.close()
    log = os.path.join(tempfile.gettempdir(), "sourcedrecall-hook.log")
    with open(log, "a") as lf:
        subprocess.Popen([sys.executable, "-m", "sourcedrecall.claude_hooks",
                          "_worker", job.name],
                         stdin=subprocess.DEVNULL, stdout=lf, stderr=lf,
                         start_new_session=True)
    return {"stored": "pending", "job": job.name, "log": log}


def session_start(event, owner=None, max_facts=15):
    """-> the JSON Claude Code adds to the session's context, or None when
    there is nothing to say (an empty memory adds no noise)."""
    # The briefing needs no retrieval model; skip the NLI conflict model so a
    # session starts in well under a second.
    os.environ.setdefault("RG_NLI", "0")
    pm = _setup_env(owner)
    st = pm.profile_status()
    if not (st.get("asserted") or st.get("provisional")):
        return None
    block = pm.profile_context(None, max_facts)["block"]
    return {"hookSpecificOutput": {"hookEventName": "SessionStart",
                                   "additionalContext": block[:9500]}}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sourcedrecall-hook")
    ap.add_argument("event", choices=["session-end", "session-start", "_worker"])
    ap.add_argument("job", nargs="?")
    ap.add_argument("--owner", default=os.environ.get("SOURCEDRECALL_OWNER"))
    ap.add_argument("--sync", action="store_true",
                    help="session-end: ingest in this process (for testing)")
    a = ap.parse_args(argv)
    if a.event == "_worker":
        job = json.load(open(a.job))
        try:
            out = ingest_session(job["transcript_path"], job["session_id"],
                                 job.get("owner"))
            print(json.dumps({"session": job["session_id"], **out}), flush=True)
        finally:
            os.unlink(a.job)
        return 0
    try:
        event = json.load(sys.stdin)
    except ValueError:
        event = {}
    if a.event == "session-end":
        out = session_end(event, a.owner, sync=a.sync)
        if a.sync:
            print(json.dumps(out))
        return 0
    out = session_start(event, a.owner)
    if out:
        print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
