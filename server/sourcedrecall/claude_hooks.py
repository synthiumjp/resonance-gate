"""Automatic memory for Claude Code: two hooks.

    sourcedrecall-hook session-end   --owner "Your Name"   (SessionEnd)
    sourcedrecall-hook session-start --owner "Your Name"   (SessionStart)

The same two commands serve Codex CLI and Gemini CLI with --agent codex or
--agent gemini (2026-10-05): both send session_id, transcript_path and cwd on
stdin at SessionStart and SessionEnd, and accept the same
hookSpecificOutput.additionalContext and systemMessage back. Only the
transcript file differs; importers.py reads those. `cursor` is a third
command for Cursor, whose payloads differ; see cursor_hooks.py.

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
import sourcedrecall.paths  # noqa: F401  (offline mode first)
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
    r"|<bash-input>|<bash-stdout>|<bash-stderr>|<task-notification>|Caveat:"
    # 2026-10-14 (JP's first real session): the summary Claude Code writes
    # when a session continues after its context ran out
    r"|This session is being continued from a previous conversation"
    # 2026-10-21 (review): written by Claude Code when the user presses Esc
    r"|\[Request interrupted by user)", re.S)
_INJECTED = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)
# 2026-10-14 (JP's first real session: '</pasted_content id="a090">' stored in
# a fact): the tags Claude Code wraps around pasted text; the text stays
_PASTE_TAGS = re.compile(r"</?pasted_content\b[^>]*>")
# the memory's own block quoted back: its header to its rules line, or, for a
# block cut short, the header and the "- ..." lines under it. 2026-10-12
# (review 3.10): it ran to the end of the message, so typing "[MEMORY" in a
# message lost everything after it.
_OWN_SUMMARY = re.compile(r"\[MEMORY[^\]]*\](?:.*?\[MEMORY RULES\][^\n]*|(?:\s*\n\s*-[^\n]*)+)", re.S)


def _text_items(content):
    if isinstance(content, str):
        return [content]
    out = []
    for it in content or []:
        if isinstance(it, dict) and it.get("type") == "text":
            out.append(it.get("text") or "")
    return out


# user-role lines skipped for a turnOrigin value not known here, by value,
# from the last read_transcript call (reported in hook.log by ingest_session)
_unknown_origins = {}


def read_transcript(path):
    """-> (turns, first_timestamp). turns: [{"role", "content"}], oldest
    first, consecutive assistant chunks merged into one turn."""
    turns, first_ts = [], None
    _unknown_origins.clear()
    # 2026-10-21 (review): one line that is not UTF-8 ended the whole read
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                o = json.loads(line)
            except ValueError:
                continue
            if o.get("isSidechain") or o.get("isMeta"):
                continue
            # 2026-10-12 (review): user-role lines the person did not type --
            # the summary Claude Code writes after /compact, background-task
            # and subagent results, messages from other sessions
            origin = o.get("turnOrigin")
            if o.get("isCompactSummary") or o.get("isVisibleInTranscriptOnly"):
                continue
            if origin not in (None, "human"):
                # 2026-10-21 (review): only "task_notification" and "peer" are
                # seen in real transcripts; a new value is counted, so a
                # Claude Code change that marks typed prompts differently
                # shows in hook.log instead of silently storing nothing
                if origin not in ("task_notification", "peer") and o.get("type") == "user":
                    _unknown_origins[str(origin)] = _unknown_origins.get(str(origin), 0) + 1
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
                text = _PASTE_TAGS.sub("\n\n", text).strip()
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
        with open(transcript_path, encoding="utf-8", errors="replace") as fh:
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


#: Agents whose session-end / session-start events carry the same fields as
#: Claude Code's (session_id, transcript_path, cwd). "name" is how the user
#: notice refers to the assistant. 2026-10-05: Codex CLI (hooks documented at
#: https://learn.chatgpt.com/docs/hooks, schemas in openai/codex
#: codex-rs/hooks/schema/generated) and Gemini CLI (docs/hooks/reference.md in
#: google-gemini/gemini-cli) both send that payload; only the transcript file
#: differs, and importers.py reads those.
AGENTS = {"claude": "Claude", "codex": "Codex", "gemini": "Gemini"}


def read_session(agent, path, session_id):
    """-> (turns, first_timestamp, conversation_id) for a transcript written
    by `agent`. The conversation id is the one `sourcedrecall-import` would
    use for the same file, so a session stored by hook and again by hand is
    not stored twice."""
    if agent == "claude":
        turns, first_ts = read_transcript(path)
        return turns, first_ts, f"claude-code:{session_id}"
    from sourcedrecall import importers
    if agent == "codex":
        turns = list(importers.codex_turns(path))
        sid = importers.codex_session_id(path) or session_id
        return turns, importers.codex_first_timestamp(path), f"codex:{sid}"
    if agent == "gemini":
        turns = list(importers.gemini_turns(path))
        sid = importers.gemini_session_id(path) or session_id
        return turns, importers.gemini_first_timestamp(path), sid
    raise ValueError("unknown agent " + repr(agent))


def ingest_turns(turns, conversation_id, first_ts=None, owner=None, cwd=None):
    """Store turns the way every hook does. Safe to repeat: only turns not
    already stored are added."""
    if not any(t["role"] == "user" for t in turns):
        return {"stored": False, "reason": "no user speech in this session"}
    pm = _setup_env(owner)
    title = next(t["content"] for t in turns if t["role"] == "user")
    # 2026-10-12 (review 3.6): scrubbed before it is cut; cut first, a key
    # split at character 60 was too short for the filter to recognise
    from sourcedrecall.secrets import scrub
    title = " ".join(scrub(title).split())[:60]
    from sourcedrecall.paths import current_scope
    return pm.profile_ingest(turns, conversation_id=conversation_id,
                             title=title,
                             owner_name=os.environ.get("SOURCEDRECALL_OWNER"),
                             date=first_ts, scope=current_scope(cwd))


def ingest_session(transcript_path, session_id, owner=None, cwd=None,
                   agent="claude"):
    """The worker: store one session. Safe to repeat -- a resumed session
    re-sends its whole transcript and only new turns are added."""
    turns, first_ts, conv_id = read_session(agent, transcript_path, session_id)
    unknown = dict(_unknown_origins) if agent == "claude" else {}
    out = ingest_turns(turns, conv_id, first_ts, owner,
                       cwd or _cwd_of(transcript_path))
    if unknown:
        out = dict(out, skipped_unknown_origin=unknown)
    return out


def session_end(event, owner=None, sync=False, agent="claude"):
    path, sid = event.get("transcript_path"), event.get("session_id")
    if not path or not sid or not os.path.exists(path):
        return {"stored": False, "reason": "no transcript"}
    cwd = event.get("cwd")
    if sync:
        return ingest_session(path, sid, owner, cwd, agent)
    return launch_worker({"transcript_path": path, "session_id": sid,
                          "owner": owner, "cwd": cwd, "agent": agent})


def _hook_log():
    # 2026-10-09 (security review): in the private state dir, not a
    # predictable /tmp path anyone can read or pre-create as a symlink
    from sourcedrecall.paths import private_dir, state_dir
    return os.path.join(private_dir(state_dir()), "hook.log")


def launch_worker(payload):
    """Store a session in a detached process (loading the parser takes
    seconds) and return at once. The job file stays in the state dir until
    its worker is done.
    2026-10-20 (JP's install): a worker was killed partway (the session's
    turns were saved, its facts never were) and nothing said so; on WSL the
    Linux side stops soon after the last terminal closes. The worker now
    logs when it starts, and the next session start reruns a job whose
    worker is gone (_rerun_orphans)."""
    from sourcedrecall.paths import jobs_dir
    job = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                      prefix="sourcedrecall-job-", dir=jobs_dir())
    json.dump(payload, job)
    job.close()
    log = _hook_log()
    _spawn_worker(job.name, log)
    return {"stored": "pending", "job": job.name, "log": log}


def _spawn_worker(job, log):
    from sourcedrecall.paths import detached
    with open(log, "a", encoding="utf-8") as lf:
        subprocess.Popen([sys.executable, "-m", "sourcedrecall.claude_hooks",
                          "_worker", job],
                         stdin=subprocess.DEVNULL, stdout=lf, stderr=lf,
                         **detached())


def _try_lock(fh):
    """-> True when this process now holds the job's lock: no worker is
    running it. The lock goes when the file is closed or the process dies."""
    try:
        if os.name == "nt":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def _rerun_orphans(min_age=60, max_tries=3, max_spawn=2, keep_days=30):
    """At session start: a job file older than a minute that no worker holds
    was left by a worker that died or failed. Start it again, at most
    max_tries times; after that it is renamed .failed and the log says so.
    Storing a session twice is harmless (turns already parsed come from the
    cache). 2026-10-21 (review): at most max_spawn workers per session start
    (each loads a 0.5 GB parser; a week of orphans used to start at once);
    the lock is held until the job is rewritten, and its age checked again
    under the lock, so two session starts cannot both count a try; a job
    that is not a JSON object is given up at once; .failed files older than
    keep_days and stray .tmp files are removed."""
    import glob
    import time
    from sourcedrecall.paths import jobs_dir
    jd = jobs_dir()
    now = time.time()
    for p in glob.glob(os.path.join(jd, "sourcedrecall-job-*.failed")) + \
            glob.glob(os.path.join(jd, "sourcedrecall-job-*.tmp")):
        try:
            age = now - os.path.getmtime(p)
            if age > (keep_days * 86400 if p.endswith(".failed") else 3600):
                os.unlink(p)
        except OSError:
            pass
    spawned = 0
    for p in sorted(glob.glob(os.path.join(jd, "sourcedrecall-job-*.json"))):
        if spawned >= max_spawn:
            break
        try:
            if time.time() - os.path.getmtime(p) < min_age:
                continue
            fh = open(p, encoding="utf-8")
        except OSError:
            continue
        log = _hook_log()
        with fh:
            if not _try_lock(fh):
                continue
            try:
                if time.time() - os.path.getmtime(p) < min_age:
                    continue        # another session start has just taken it
            except OSError:
                continue            # gone: its worker finished meanwhile
            try:
                job = json.load(fh)
            except ValueError:
                job = None
            ok = isinstance(job, dict)
            sid = (job.get("session_id") or job.get("conversation_id")) if ok else None
            tries = job.get("tries", 0) if ok and isinstance(job.get("tries", 0), int) else max_tries
            if tries >= max_tries:
                failed = p[:-len(".json")] + ".failed"
                if os.name == "nt":
                    fh.close()      # Windows cannot rename an open file
                os.replace(p, failed)
                with open(log, "a", encoding="utf-8") as lf:
                    lf.write(json.dumps({"session": sid, "gave_up": True, "tries": tries,
                                         "job": failed}) + "\n")
                continue
            job["tries"] = tries + 1
            tmp = p + ".tmp"
            with open(tmp, "w", encoding="utf-8") as out:
                json.dump(job, out)
            if os.name == "nt":
                fh.close()
            os.replace(tmp, p)      # also renews its age: not rerun again at once
        with open(log, "a", encoding="utf-8") as lf:
            lf.write(json.dumps({"session": sid, "rerun": job["tries"]}) + "\n")
        _spawn_worker(p, log)
        spawned += 1


def _session_start(event, owner=None, max_facts=15, agent="claude",
                  show_notice=True):
    """-> the JSON Claude Code adds to the session's context, or None when
    there is nothing to say (an empty memory adds no noise). show_notice=False
    for a host that has no way to show the user a message: reporting what was
    saved marks it as reported, so it must not be done unseen."""
    # Some people want memory only when they ask for it (research into what
    # users want, 2026-10-02: "I prefer claude's opt in implementation").
    # SOURCEDRECALL_BRIEFING=off: no summary at session start; the tools still
    # work, and sessions are still stored.
    off = ("off", "0", "false", "no")
    briefing = os.environ.get("SOURCEDRECALL_BRIEFING", "on").lower() not in off
    notice = show_notice and (
        os.environ.get("SOURCEDRECALL_NOTICE", "on").lower() not in off)
    if not (briefing or notice):
        return None
    # The briefing needs no retrieval model; skip the NLI conflict model so a
    # session starts in well under a second.
    os.environ.setdefault("RG_NLI", "0")
    pm = _setup_env(owner)
    st = pm.profile_status()
    if not (st.get("asserted") or st.get("provisional")):
        return _welcome(agent) if notice else None
    out = {}
    if briefing:
        from sourcedrecall.paths import current_scope
        block = pm.profile_context(None, max_facts,
                                   scope=current_scope(event.get("cwd")))["block"]
        out["hookSpecificOutput"] = {"hookEventName": "SessionStart",
                                     "additionalContext": block[:9500]}
    if notice:
        msg = saved_notice(pm.profile_news(), pm.memory_file(), agent=agent)
        if msg:
            out["systemMessage"] = msg
    return out or None


def session_start(event, owner=None, max_facts=15, agent="claude",
                  show_notice=True):
    try:
        _rerun_orphans()
    except Exception as e:          # never stop a session starting
        print(f"sourcedrecall: could not check for unfinished sessions: {e!r}",
              file=sys.stderr)
    out = _session_start(event, owner, max_facts, agent, show_notice)
    note = _windows_tools_note(agent, owner) if show_notice else None
    if note:
        out = dict(out or {})
        out["systemMessage"] = ((out.get("systemMessage") or "") + "\n\n" + note).strip()
    return out


def _windows_tools_note(agent, owner=None):
    """2026-10-13 (Claude Code on native Windows, tested): it cannot start
    the plugin's MCP launcher (an extensionless bash script; `bash` there
    can be the WSL stub), so the memory tools are missing while the hooks
    (run through Git Bash) work. Registering the installed server program
    directly connects. Once, as the plugin, on Windows: the exact command."""
    if os.name != "nt" or agent != "claude" or not os.environ.get("CLAUDE_PLUGIN_ROOT"):
        return None
    from sourcedrecall.paths import state_dir
    mark = os.path.join(state_dir(), ".windows-tools-told")
    exe = os.path.join(os.path.dirname(sys.executable), "sourcedrecall.exe")
    if os.path.exists(mark) or not os.path.exists(exe):
        return None
    try:
        os.makedirs(state_dir(), exist_ok=True)
        open(mark, "w").close()
    except OSError:
        return None
    who = owner or os.environ.get("SOURCEDRECALL_OWNER") or "Your Name"
    return ("sourcedrecall on Windows: your sessions are stored and summarised, but Claude Code "
            "cannot start the plugin's memory tools by itself on Windows. To turn them on, run "
            f"once in a terminal:\n  claude mcp add sourcedrecall -s user -e SOURCEDRECALL_OWNER=\"{who}\" "
            f"-- \"{exe}\"\nthen restart Claude Code.")


def _welcome(agent):
    """2026-10-12 (launch review: a new user saw nothing at all until a
    second session). Once, while the memory is empty: what happens next,
    shown to the user only."""
    from sourcedrecall.paths import state_dir
    mark = os.path.join(state_dir(), ".welcomed")
    if os.path.exists(mark):
        return None
    # 2026-10-14 (JP's first session): "your memory is empty" while the
    # session that had just ended was still being stored. A job file is
    # removed by its worker when done (one older than 30 minutes is a leftover)
    import glob
    import time
    from sourcedrecall.paths import command, jobs_dir
    pending = [p for p in glob.glob(os.path.join(jobs_dir(), "sourcedrecall-job-*.json"))
               if time.time() - os.path.getmtime(p) < 1800]
    if pending:
        return {"systemMessage": (
            "sourcedrecall is installed. Your last session is being stored now; the "
            "next session starts with what was kept. To see what is stored: "
            f"{command('memory show')}")}
    try:
        os.makedirs(state_dir(), exist_ok=True)
        open(mark, "w").close()
    except OSError:
        return None
    return {"systemMessage": (
        "sourcedrecall is installed and your memory is empty. This session is "
        "stored when it ends, and the next one starts with what was kept. "
        f"To bring in past chats: {command('import chatgpt <export.zip>')} (or "
        f"claude). To see what is stored: {command('memory show')} ; what the "
        f"agent was last given: {command('memory last')}")}


def saved_notice(new, memory_file=None, show=3, agent="claude"):
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
    tail = f"Ask {AGENTS.get(agent, 'the assistant')} to forget any of them by id"
    if memory_file:
        tail += f", or see {memory_file}"
    return " ".join(parts) + " " + tail + "."


def main(argv=None):
    # 2026-10-14: conversations with an assistant (rgx RGX_ASSISTANT_CHAT)
    os.environ.setdefault("RGX_ASSISTANT_CHAT", "1")
    ap = argparse.ArgumentParser(prog="sourcedrecall-hook")
    ap.add_argument("event", choices=["session-end", "session-start", "cursor",
                                      "_worker", "_pending"])
    ap.add_argument("job", nargs="?")
    ap.add_argument("--owner", default=os.environ.get("SOURCEDRECALL_OWNER"))
    ap.add_argument("--agent", choices=sorted(AGENTS), default="claude",
                    help="session-end / session-start: which agent's "
                         "transcript and wording (default claude)")
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
            # 2026-10-21 (review): one session that fails no longer stops
            # the ones queued after it
            try:
                out = ingest_session(path, sid, a.owner, ev.get("cwd"))
            except Exception as e:
                print(json.dumps({"session": sid, "queued": True,
                                  "error": f"{type(e).__name__}: {e}"}), flush=True)
                continue
            print(json.dumps({"session": sid, "queued": True, **out}), flush=True)
        os.unlink(a.job)
        return 0
    if a.event == "_worker":
        try:
            fh = open(a.job, encoding="utf-8")
        except OSError:
            return 0                # already stored by another worker
        try:
            job = json.load(fh)
        except ValueError:
            job = None
        if not isinstance(job, dict):
            fh.close()              # left for the next session start to give up on
            print(json.dumps({"job": a.job, "error": "the job file is not a JSON object"}),
                  flush=True)
            return 1
        if not _try_lock(fh):
            fh.close()
            return 0                # another worker is storing it
        # a "started" line without a result after it: the worker was killed
        from datetime import datetime, timezone
        print(json.dumps({"session": job.get("session_id") or job.get("conversation_id"),
                          "started": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                          **({"rerun": job["tries"]} if job.get("tries") else {})}),
              flush=True)
        try:
            if job.get("spool"):
                from sourcedrecall import cursor_hooks
                out = cursor_hooks.ingest_spool(
                    job["spool"], job["conversation_id"], job.get("owner"),
                    job.get("cwd"), job.get("delete", False))
            else:
                out = ingest_session(job["transcript_path"], job["session_id"],
                                     job.get("owner"), job.get("cwd"),
                                     job.get("agent", "claude"))
            print(json.dumps({"session": job.get("session_id")
                              or job.get("conversation_id"), **out}), flush=True)
        except BaseException:
            # 2026-10-21 (review): the job used to be removed on an error too,
            # so a session that failed to store was lost with only a
            # traceback in the log. It now stays for the next session start
            # (at most three tries, then .failed and a log line).
            fh.close()
            raise
        # Windows cannot remove an open file; elsewhere the lock is kept
        # until the file is gone, so a session start cannot rerun it
        if os.name == "nt":
            fh.close()
        try:
            os.unlink(a.job)
        except OSError:
            pass
        fh.close()
        return 0
    try:
        # utf-8 whatever the console's code page (Windows; review 3.10)
        buf = getattr(sys.stdin, "buffer", None)
        raw = buf.read().decode("utf-8", "replace") if buf else sys.stdin.read()
        event = json.loads(raw)
    except ValueError as e:
        # 2026-10-13 (clean-install test on Windows): unreadable input was
        # skipped without a trace; say so where a user can find it
        msg = f"sourcedrecall: {a.event}: the hook input is not JSON ({e}); nothing stored"
        print(msg, file=sys.stderr)
        try:
            from sourcedrecall.paths import private_dir, state_dir
            with open(os.path.join(private_dir(state_dir()), "hook.log"), "a", encoding="utf-8") as lf:
                lf.write(msg + "\n")
        except OSError:
            pass
        event = {}
    if not isinstance(event, dict):
        event = {}
    if a.event == "cursor":
        from sourcedrecall import cursor_hooks
        print(json.dumps(cursor_hooks.handle(event, a.owner, sync=a.sync)))
        return 0
    if a.event == "session-end":
        out = session_end(event, a.owner, sync=a.sync, agent=a.agent)
        if a.sync:
            print(json.dumps(out))
        return 0
    out = session_start(event, a.owner, agent=a.agent)
    if out:
        print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
