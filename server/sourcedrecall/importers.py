"""Import a coding-CLI session file, or a chat app's data export, into the
memory.

    sourcedrecall-import gemini  <session file> [--id ID] [--date D] [--scope S]
    sourcedrecall-import codex   <rollout file>  [--id ID] [--date D] [--scope S]
    sourcedrecall-import chatgpt <export .zip or conversations.json>
    sourcedrecall-import claude  <export .zip or conversations.json>

Each parser yields {"role": "user"|"assistant", "content": str} dicts and
does not touch the memory. main() feeds them to profile_ingest, the same
call `sourcedrecall-memory ingest` makes.

Gemini: the layout comes from the chat-recording code in the official
google-gemini/gemini-cli repository (packages/core/src/services/
chatRecordingService.ts). The public docs only say sessions live in
~/.gemini/tmp/<project_hash>/chats/ and do not describe the file, so this
is verified against source, not against documentation.

ChatGPT and Claude.ai (2026-10-05): people moving between assistants want
to bring what the old one knew (research into what users want, 2026-10-05).
Both apps' "export your data" archives hold a conversations.json. Neither
company documents its layout; the shapes read here are the ones the export
has had since 2023 and that open-source export viewers parse. Only the
visible text of the conversation is read: no tool output, hidden context,
reasoning summaries or attached files. Each conversation is stored with its
own date and id, so importing the same export again adds nothing new.

Codex CLI (2026-10-05): read from the open-source openai/codex repository
(Rust, under codex-rs) at main commit 7f892275e3 (2026-10-04; latest release
tag then rust-v0.160.0). OpenAI's public docs do not describe the rollout
file (~/.codex/sessions/YYYY/MM/DD/rollout-<timestamp>-<thread id>.jsonl),
so the layouts below come from source. Two layouts exist.

  Layout A, from 2025-05-07 to rust-v0.32.0. Written by
  codex-rs/core/src/rollout.rs (added in 42617f8726, "feat: save session
  transcripts when using Rust CLI", 2025-05-07; later core/src/rollout/
  recorder.rs). Line 1 is a bare session header
  {"id", "timestamp", "instructions"[, "git"]}. Every later line is a raw
  ResponseItem: {"type": "message", "role": "user"|"assistant",
  "content": [{"type": "input_text"|"output_text", "text": ...}]}, or a
  function call or its output, or {"record_type": "state", ...}. (Checked in
  core/src/rollout.rs and core/src/models.rs at rust-v0.0.2505101753, and
  in RolloutRecorder::resume at rust-v0.9.0.)

  Layout B, rust-v0.33.0 to now (rust-v0.32.0 has no RolloutLine). Each line
  is a RolloutLine: {"timestamp", "type", "payload"}, "type" being
  session_meta, response_item, event_msg, compacted, turn_context, and later
  token_usage_record, world_state, retained_context and others. RolloutLine
  and RolloutItem are in codex-rs/protocol/src/protocol.rs at rust-v0.33.0
  and in codex-rs/history/src/lib.rs and history/src/rollout_payload.rs now
  (serde tag = "type", content = "payload"). A response_item payload is the
  same ResponseItem as in layout A (codex-rs/protocol/src/models.rs).
  codex-rs/rollout/src/policy.rs decides what is written: every
  ResponseItem::Message is kept in every history mode, while the event_msg
  user_message and agent_message copies are written only in Legacy history
  mode. This reader therefore takes the response_item messages and ignores
  those events, which also keeps a message from being stored twice. Newer
  files can be compressed as .jsonl.zst (rollout/src/compression.rs).

Read: user and assistant messages, their input_text and output_text parts.
Skipped: developer and system messages, reasoning, function and tool calls
and their output, compacted items, turn context, and every user-role
message Codex itself injected. Codex recognises those by their text, in
codex-rs/core/src/context/contextual_user_message.rs
(CONTEXTUAL_USER_FRAGMENT_MATCHERS) and the marker definitions beside it:
"# AGENTS.md instructions ... </INSTRUCTIONS>" (older: "<user_instructions>"),
"<environment_context>", "<user_shell_command>", "<turn_aborted>",
"<subagent_notification>", "<skill>", "<hook_prompt ...>",
"<codex_internal_context ...>", "<goal_context>", "<external_KEY>...",
"<agent_message_board_notification>", three "Warning: ..." lines from old
versions, the plugin recommendation intro, and the compaction summary
prefix (codex-rs/prompts/templates/compact/summary_prefix.md). Codex drops
a whole message if any part matches; so does this reader. The
"## My request for Codex:" prefix some callers put before a request is
removed (protocol.rs, strip_user_message_prefix). An event_msg of type
thread_rolled_back (num_turns) removes the last num_turns user turns, as
Codex's own history does (core/src/context_manager/history.rs,
drop_last_n_user_turns); after a compaction that count is applied to the
turns this reader can see, which may differ from Codex's. Sub-agent and
internal rollouts (session_meta "source" of subagent or internal) are not
read: their user messages are synthetic.
"""
import sourcedrecall.paths  # noqa: F401  (offline mode first)
import argparse
import json
import os
import re
import sys


def _text_of(content):
    """Text from a Gemini PartListUnion: a string, a part, or a list of them.
    Parts marked as thoughts and non-text parts (calls, responses) are skipped."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        if content.get("thought"):
            return ""
        t = content.get("text")
        return t if isinstance(t, str) else ""
    if isinstance(content, list):
        return "".join(_text_of(c) for c in content)
    return ""


def _gemini_messages(path):
    """Message records in order, after applying $rewindTo and $patch removals.
    Accepts the older single-JSON file ({"messages": [...]}) and the JSONL
    form (header line, message lines, $set / $rewindTo / $patch lines)."""
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    try:
        whole = json.loads(raw)
    except ValueError:
        whole = None
    if isinstance(whole, dict) and isinstance(whole.get("messages"), list):
        return whole["messages"], whole.get("sessionId")
    msgs, session_id = [], None
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if not isinstance(rec, dict):
            continue
        if "$rewindTo" in rec:
            ids = [m.get("id") for m in msgs]
            if rec["$rewindTo"] in ids:
                msgs = msgs[:ids.index(rec["$rewindTo"])]
        elif "$patch" in rec:
            gone = set((rec["$patch"] or {}).get("removeIds") or [])
            msgs = [m for m in msgs if m.get("id") not in gone]
        elif "$set" in rec:
            session_id = (rec["$set"] or {}).get("sessionId", session_id)
        elif rec.get("type") in ("user", "gemini"):
            same = [i for i, m in enumerate(msgs) if m.get("id") == rec.get("id")]
            if same and rec.get("id") is not None:
                msgs[same[0]] = rec          # a later line replaces the message
            else:
                msgs.append(rec)
        elif "sessionId" in rec:
            session_id = rec["sessionId"]
    return msgs, session_id


def gemini_session_id(path):
    return _gemini_messages(path)[1]


def gemini_turns(path):
    """Yield {"role", "content"} for each user / gemini message with text."""
    msgs, _ = _gemini_messages(path)
    for m in msgs:
        role = {"user": "user", "gemini": "assistant"}.get(m.get("type"))
        if not role:
            continue
        text = _text_of(m.get("content")).strip()
        if text:
            yield {"role": role, "content": text}


def gemini_first_timestamp(path):
    """ISO timestamp of the first user message, or None."""
    msgs, _ = _gemini_messages(path)
    for m in msgs:
        if m.get("type") == "user" and m.get("timestamp"):
            return m["timestamp"]
    return None


# ---- Codex CLI rollouts (see the module docstring for the source) ---------

_CODEX_WRAPPED = tuple((a.lower(), b.lower()) for a, b in (
    ("# AGENTS.md instructions", "</INSTRUCTIONS>"),
    ("<user_instructions>", "</user_instructions>"),
    ("<environment_context>", "</environment_context>"),
    ("<user_shell_command>", "</user_shell_command>"),
    ("<turn_aborted>", "</turn_aborted>"),
    ("<subagent_notification>", "</subagent_notification>"),
    ("<skill>", "</skill>"),
    ("<codex_internal_context", "</codex_internal_context>"),
    ("<goal_context>", "</goal_context>"),
    ("<agent_message_board_notification>", "</agent_message_board_notification>"),
))
_CODEX_EXTERNAL = re.compile(r"^<external_([^>]*)>.*</external_\1>$", re.S)
_CODEX_HOOK_PROMPT = re.compile(r"^<hook_prompt\b.*</hook_prompt>$", re.S)
_CODEX_PLAIN_STARTS = (
    "Warning: Your account was flagged for potentially high-risk cyber activity",
    "Warning: The maximum number of unified exec processes you can keep open is",
    "Here is a list of plugins that are available but not installed.",
    "Another language model started to solve this problem and produced a "
    "summary of its thinking process.",       # compaction summary prefix
)
_CODEX_MEDIA_LABEL = re.compile(
    r'^(</?(image|audio)>|<(image|audio) name=.*>)$', re.S)
_CODEX_REQUEST_MARK = "## My request for Codex:"


def _codex_is_injected(text):
    t = text.strip()
    low = t.lower()
    if any(low.startswith(a) and low.endswith(b) for a, b in _CODEX_WRAPPED):
        return True
    if _CODEX_EXTERNAL.match(t) or _CODEX_HOOK_PROMPT.match(t):
        return True
    if any(t.startswith(p) for p in _CODEX_PLAIN_STARTS):
        return True
    return (t.startswith("Warning: apply_patch was requested via ")
            and t.endswith("Use the apply_patch tool instead of exec_command."))


def _codex_message_text(role, content):
    """The visible text of one message item, or "" when it is not speech."""
    if not isinstance(content, list):
        return ""
    want = "input_text" if role == "user" else "output_text"
    parts = []
    for part in content:
        if not isinstance(part, dict) or part.get("type") != want:
            continue
        text = part.get("text")
        if not isinstance(text, str):
            continue
        if role == "user":
            if _codex_is_injected(text):
                return ""             # Codex drops the whole message too
            if _CODEX_MEDIA_LABEL.match(text.strip()):
                continue
        parts.append(text)
    text = "\n".join(parts)
    if role == "user" and _CODEX_REQUEST_MARK in text:
        text = text[text.index(_CODEX_REQUEST_MARK) + len(_CODEX_REQUEST_MARK):]
    return text.strip()


def _codex_open(path):
    path = str(path)
    if not path.endswith(".zst"):
        return open(path, encoding="utf-8")
    import io
    try:
        from compression import zstd              # Python 3.14+
        return io.TextIOWrapper(zstd.open(path, "rb"), encoding="utf-8")
    except ImportError:
        pass
    try:
        import zstandard
    except ImportError:
        raise ValueError(
            path + " is zstd-compressed (Codex writes .jsonl.zst for older "
            "sessions). Decompress it first (`zstd -d`), or use Python 3.14 "
            "or install the `zstandard` package.")
    return io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(
        open(path, "rb")), encoding="utf-8")


def _codex_read(path):
    """-> (turns, session_id, first_timestamp, skipped). turns is a list of
    {"role", "content"}; skipped is True for a sub-agent or internal rollout."""
    turns = []        # [{"role", "content", "user_turn": bool}]
    meta_id = None
    first_ts = header_ts = None
    skipped = False
    with _codex_open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if not isinstance(rec, dict):
                continue
            ts = rec.get("timestamp")
            item = None
            kind = rec.get("type")
            if kind == "message":                         # layout A item
                item = rec
            elif kind is None and "id" in rec and "timestamp" in rec \
                    and meta_id is None:                  # layout A header
                meta_id = rec.get("id")
                header_ts = ts
                continue
            elif isinstance(rec.get("payload"), dict):    # layout B
                payload = rec["payload"]
                if kind == "session_meta":
                    if meta_id is None:
                        meta_id = payload.get("id")
                        header_ts = payload.get("timestamp") or ts
                        src = payload.get("source")
                        if isinstance(src, dict) and (
                                "subagent" in src or "internal" in src):
                            skipped = True
                    continue
                if kind == "response_item" and payload.get("type") == "message":
                    item = payload
                elif kind == "event_msg" and payload.get("type") == "thread_rolled_back":
                    n = payload.get("num_turns")
                    if isinstance(n, int) and n > 0:
                        starts = [i for i, t in enumerate(turns) if t["user_turn"]]
                        cut = starts[-n] if n <= len(starts) else (
                            starts[0] if starts else len(turns))
                        del turns[cut:]
                    continue
            if item is None:
                continue
            role = item.get("role")
            if role not in ("user", "assistant"):
                continue
            text = _codex_message_text(role, item.get("content"))
            if not text:
                continue
            if role == "user" and first_ts is None:
                first_ts = ts
            turns.append({"role": role, "content": text,
                          "user_turn": role == "user"})
    for t in turns:
        del t["user_turn"]
    return turns, meta_id, first_ts or header_ts, skipped


_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                   r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


def codex_session_id(path):
    """The thread id: the uuid in the file name (rollout-<time>-<uuid>.jsonl,
    which is what Codex itself treats as canonical), else the id in the
    session header."""
    m = _UUID.search(os.path.basename(str(path)))
    if m:
        return m.group(0)
    return _codex_read(path)[1]


def codex_first_timestamp(path):
    return _codex_read(path)[2]


def codex_turns(path):
    """Yield {"role", "content"} for each user and assistant message in a
    Codex rollout file, in order. Nothing for a sub-agent rollout."""
    turns, _, _, skipped = _codex_read(path)
    if skipped:
        return
    yield from turns


def _export_json(path):
    """conversations.json from an export: the .zip, its folder, or the file."""
    import zipfile
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            name = next((n for n in z.namelist()
                         if os.path.basename(n) == "conversations.json"), None)
            if name is None:
                raise ValueError("no conversations.json in " + path)
            return json.loads(z.read(name).decode("utf-8"))
    if os.path.isdir(path):
        path = os.path.join(path, "conversations.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _day(value):
    """'YYYY-MM-DD' from epoch seconds or an ISO timestamp (UTC)."""
    from datetime import datetime, timezone
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).strftime("%Y-%m-%d")
    if isinstance(value, str) and len(value) >= 10:
        return value[:10]
    return None


def _chatgpt_branch(mapping, current):
    """The messages on the branch the user last saw, oldest first: from
    current_node up through the parents. An edited message leaves its old
    branch in the mapping; that branch is not what the conversation became."""
    if current not in mapping:
        # no current node recorded: the most recent leaf
        leaves = [k for k, v in mapping.items() if not v.get("children")]
        current = max(leaves, default=None, key=lambda k: (
            ((mapping[k].get("message") or {}).get("create_time")) or 0))
    out, seen = [], set()
    while current in mapping and current not in seen:
        seen.add(current)
        node = mapping[current]
        if node.get("message"):
            out.append(node["message"])
        current = node.get("parent")
    return out[::-1]


def _chatgpt_text(msg):
    content = msg.get("content") or {}
    if content.get("content_type") not in ("text", "multimodal_text"):
        return ""     # code, tool output, quotes, custom instructions, thoughts
    meta = msg.get("metadata") or {}
    if meta.get("is_visually_hidden_from_conversation"):
        return ""
    parts = content.get("parts") or []
    return "\n".join(p for p in parts if isinstance(p, str)).strip()


def chatgpt_conversations(path):
    """Yield (id, title, date, turns) for each conversation in a ChatGPT
    export, turns as {"role", "content"} in order."""
    for conv in _export_json(path):
        if not isinstance(conv, dict):
            continue
        turns = []
        for m in _chatgpt_branch(conv.get("mapping") or {}, conv.get("current_node")):
            role = ((m.get("author") or {}).get("role"))
            if role not in ("user", "assistant"):
                continue
            text = _chatgpt_text(m)
            if text:
                turns.append({"role": role, "content": text})
        cid = conv.get("conversation_id") or conv.get("id")
        yield (cid, conv.get("title") or "", _day(conv.get("create_time")), turns)


def claude_conversations(path):
    """Yield (id, title, date, turns) for each conversation in a Claude.ai
    export. A message's text is its "text" field, or the text parts of its
    "content" list; attachments and files are not read."""
    for conv in _export_json(path):
        if not isinstance(conv, dict):
            continue
        turns = []
        for m in conv.get("chat_messages") or []:
            role = {"human": "user", "assistant": "assistant"}.get(m.get("sender"))
            if not role:
                continue
            text = m.get("text")
            if not isinstance(text, str) or not text.strip():
                text = "\n".join(c.get("text", "") for c in m.get("content") or []
                                 if isinstance(c, dict) and c.get("type") == "text")
            text = (text or "").strip()
            if text:
                turns.append({"role": role, "content": text})
        yield (conv.get("uuid"), conv.get("name") or "", _day(conv.get("created_at")),
               turns)


def _import_export(fmt, path, owner, as_json):
    from sourcedrecall import profile_memory as pm
    convs = (chatgpt_conversations if fmt == "chatgpt" else claude_conversations)(path)
    n_conv = n_turns = n_facts = 0
    for cid, title, date, turns in convs:
        if not cid or not any(t["role"] == "user" for t in turns):
            continue
        out = pm.profile_ingest(turns, conversation_id=f"{fmt}:{cid}",
                                title=title[:60] or None, owner_name=owner, date=date)
        n_conv += 1
        n_turns += out["turns"]
        n_facts += out["facts"]
        if n_conv % 50 == 0 and not as_json:
            print(f"{n_conv} conversations...", file=sys.stderr, flush=True)
    res = {"conversations": n_conv, "messages": n_turns, "facts": n_facts}
    print(json.dumps(res, indent=2) if as_json else
          f"stored {n_facts} new facts from {n_turns} messages in "
          f"{n_conv} conversations")
    return 0 if n_conv else 1


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="sourcedrecall-import",
        description="Store a Gemini or Codex CLI session, or a ChatGPT or "
                    "Claude.ai data export, in the memory.")
    ap.add_argument("format", choices=["codex", "gemini", "chatgpt", "claude"])
    ap.add_argument("file")
    ap.add_argument("--owner", default=os.environ.get("SOURCEDRECALL_OWNER"))
    ap.add_argument("--id", dest="conv_id")
    ap.add_argument("--date")
    ap.add_argument("--scope")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.format in ("chatgpt", "claude"):
        return _import_export(a.format, a.file, a.owner, a.json)
    try:
        if a.format == "gemini":
            turns = list(gemini_turns(a.file))
            sid = gemini_session_id(a.file)
            first = gemini_first_timestamp(a.file)
        else:
            turns = list(codex_turns(a.file))
            sid = codex_session_id(a.file)
            sid = f"codex:{sid}" if sid else None
            first = codex_first_timestamp(a.file)
    except (OSError, ValueError) as e:
        print(f"cannot read {a.file}: {e}", file=sys.stderr)
        return 2
    if not turns:
        print("nothing to store", file=sys.stderr)
        return 1
    conv_id = a.conv_id or sid or os.path.splitext(os.path.basename(a.file))[0]
    from sourcedrecall import profile_memory as pm
    out = pm.profile_ingest(turns, conversation_id=conv_id,
                            owner_name=a.owner, date=a.date or first,
                            scope=a.scope)
    print(json.dumps(out, indent=2) if a.json else
          f"stored {out['facts']} new facts from {out['turns']} messages "
          f"(conversation {out['conversation_id']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
