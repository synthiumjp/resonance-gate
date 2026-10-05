"""Import a coding-CLI session file, or a chat app's data export, into the
memory.

    sourcedrecall-import gemini  <session file> [--id ID] [--date D] [--scope S]
    sourcedrecall-import codex   <session file>
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

Codex: TODO. The rollout files (~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl)
are not described in OpenAI's public docs, and the line layout has changed
between versions. Nothing is implemented until it can be checked against an
official description.
"""
import argparse
import json
import os
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


def codex_turns(path):
    # TODO: not implemented. See the module docstring.
    raise NotImplementedError(
        "Codex rollout files are not documented by OpenAI, so no importer "
        "has been written. Pipe your own JSON Lines into "
        "`sourcedrecall-memory ingest` instead.")


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
        else:
            turns, sid = list(codex_turns(a.file)), None
    except NotImplementedError as e:
        print(str(e), file=sys.stderr)
        return 2
    if not turns:
        print("nothing to store", file=sys.stderr)
        return 1
    conv_id = a.conv_id or sid or os.path.splitext(os.path.basename(a.file))[0]
    from sourcedrecall import profile_memory as pm
    out = pm.profile_ingest(turns, conversation_id=conv_id,
                            owner_name=a.owner, date=a.date, scope=a.scope)
    print(json.dumps(out, indent=2) if a.json else
          f"stored {out['facts']} new facts from {out['turns']} messages "
          f"(conversation {out['conversation_id']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
