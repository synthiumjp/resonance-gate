"""Import a coding-CLI session file into the memory.

    sourcedrecall-import gemini <session file> [--id ID] [--date D] [--scope S]
    sourcedrecall-import codex  <session file>

Each parser yields {"role": "user"|"assistant", "content": str} dicts and
does not touch the memory. main() feeds them to profile_ingest, the same
call `sourcedrecall-memory ingest` makes.

Gemini: the layout comes from the chat-recording code in the official
google-gemini/gemini-cli repository (packages/core/src/services/
chatRecordingService.ts). The public docs only say sessions live in
~/.gemini/tmp/<project_hash>/chats/ and do not describe the file, so this
is verified against source, not against documentation.

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


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="sourcedrecall-import",
        description="Store a Codex or Gemini CLI session in the memory.")
    ap.add_argument("format", choices=["codex", "gemini"])
    ap.add_argument("file")
    ap.add_argument("--owner", default=os.environ.get("SOURCEDRECALL_OWNER"))
    ap.add_argument("--id", dest="conv_id")
    ap.add_argument("--date")
    ap.add_argument("--scope")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
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
