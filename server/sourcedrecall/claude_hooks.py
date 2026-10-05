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


def _cwd_of(transcript_path):
    try:
        with open(transcript_path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    o = json.loads(line)
                except ValueError:
                    continue
                if o.get("cwd"):
                    return o["cwd"]
    except OSError:
        pass
    return None


def ingest_session(transcript_path, session_id, owner=None, cwd=None):
    """The worker: store one session. Safe to repeat -- a resumed session
    re-sends its whole transcript and only new turns are added."""
    turns, first_ts = read_transcript(transcript_path)
    if not any(t["role"] == "user" for t in turns):
        return {"stored": False, "reason": "no user speech in this session"}
    pm = _setup_env(owner)
    title = next(t["content"] for t in turns if t["role"] == "user")
    title = " ".join(title.split())[:60]
    from sourcedrecall.paths import current_scope
    return pm.profile_ingest(turns, conversation_id=f"claude-code:{session_id}",
                             title=title,
                             owner_name=os.environ.get("SOURCEDRECALL_OWNER"),
                             date=first_ts,
                             scope=current_scope(cwd or _cwd_of(transcript_path)))


def session_end(event, owner=None, sync=False):
    path, sid = event.get("transcript_path"), event.get("session_id")
    if not path or not sid or not os.path.exists(path):
        return {"stored": False, "reason": "no transcript"}
    cwd = event.get("cwd")
    if sync:
        return ingest_session(path, sid, owner, cwd)
    job = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                      prefix="sourcedrecall-job-")
    json.dump({"transcript_path": path, "session_id": sid, "owner": owner,
               "cwd": cwd}, job)
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
    # Some people want memory only when they ask for it (research into what
    # users want, 2026-10-02: "I prefer claude's opt in implementation").
    # SOURCEDRECALL_BRIEFING=off: no summary at session start; the tools still
    # work, and sessions are still stored.
    off = ("off", "0", "false", "no")
    briefing = os.environ.get("SOURCEDRECALL_BRIEFING", "on").lower() not in off
    notice = os.environ.get("SOURCEDRECALL_NOTICE", "on").lower() not in off
    if not (briefing or notice):
        return None
    # The briefing needs no retrieval model; skip the NLI conflict model so a
    # session starts in well under a second.
    os.environ.setdefault("RG_NLI", "0")
    pm = _setup_env(owner)
    st = pm.profile_status()
    if not (st.get("asserted") or st.get("provisional")):
        return None
    out = {}
    if briefing:
        from sourcedrecall.paths import current_scope
        block = pm.profile_context(None, max_facts,
                                   scope=current_scope(event.get("cwd")))["block"]
        out["hookSpecificOutput"] = {"hookEventName": "SessionStart",
                                     "additionalContext": block[:9500]}
    if notice:
        msg = saved_notice(pm.profile_news(), pm.memory_file())
        if msg:
            out["systemMessage"] = msg
    return out or None


def saved_notice(new, memory_file=None, show=3):
    """The line shown to the USER (not to Claude) when a session starts:
    what was stored since they last looked, in their own words, with the id
    to forget it by. A new standing instruction is always shown in full:
    it leads every later session, and a pasted document could plant one
    (research into memory complaints, 2026-10-05: memory as an injection
    surface; silent writes)."""
    if not new:
        return None
    def words(f):
        w = " ".join((f.get("said") or f.get("text") or "").split())
        w = f'"{w[:77] + "..." if len(w) > 80 else w}"'
        return f"{w} ({f['id']})" if f.get("id") else w
    instr = [f for f in new if f.get("attribute") == "instruction"]
    rest = [f for f in new if f.get("attribute") != "instruction"]
    parts = []
    if instr:
        parts.append(f"sourcedrecall saved {len(instr)} new instruction"
                     f"{'s' if len(instr) != 1 else ''} for the assistant, "
                     "followed in every session: "
                     + ", ".join(words(f) for f in instr) + ".")
    if rest:
        n = len(rest)
        body = ", ".join(words(f) for f in rest[:show])
        if n > show:
            body += f" and {n - show} more"
        parts.append(f"sourcedrecall saved {n} new thing"
                     f"{'s' if n != 1 else ''}: {body}.")
    tail = "Ask Claude to forget any of them by id"
    if memory_file:
        tail += f", or see {memory_file}"
    return " ".join(parts) + " " + tail + "."


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sourcedrecall-hook")
    ap.add_argument("event", choices=["session-end", "session-start", "_worker",
                                      "_pending"])
    ap.add_argument("job", nargs="?")
    ap.add_argument("--owner", default=os.environ.get("SOURCEDRECALL_OWNER"))
    ap.add_argument("--sync", action="store_true",
                    help="session-end: ingest in this process (for testing)")
    a = ap.parse_args(argv)
    if a.event == "_pending":
        # sessions that ended before the install finished (or before a name
        # was set): their hook events, one per line, stored now
        try:
            lines = [l for l in open(a.job, encoding="utf-8") if l.strip()]
        except OSError:
            return 0
        for line in lines:
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            path, sid = ev.get("transcript_path"), ev.get("session_id")
            if not path or not sid or not os.path.exists(path):
                continue
            out = ingest_session(path, sid, a.owner, ev.get("cwd"))
            print(json.dumps({"session": sid, "queued": True, **out}), flush=True)
        os.unlink(a.job)
        return 0
    if a.event == "_worker":
        job = json.load(open(a.job))
        try:
            out = ingest_session(job["transcript_path"], job["session_id"],
                                 job.get("owner"), job.get("cwd"))
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
