"""sourcedrecall-memory: use the memory from a terminal, a script, or any
agent or model -- no MCP client needed.

    sourcedrecall-memory show                 print the memory (and rewrite MEMORY.md)
    sourcedrecall-memory path                 where the memory and MEMORY.md live
    sourcedrecall-memory forget <id>          remove a fact
    sourcedrecall-memory confirm <id>         mark a fact as confirmed
    sourcedrecall-memory context [question]   the text to put in any model's prompt
    sourcedrecall-memory recall <question>    what is stored about a question
    sourcedrecall-memory ingest [file]        store a conversation

`ingest` reads JSON Lines from the file or stdin, one message per line:
    {"role": "user", "content": "I moved to Brunswick last week."}
    {"role": "assistant", "content": "Congratulations on the move!"}
A JSON array of the same objects also works. Options: --owner (the person
the memory is about; default SOURCEDRECALL_OWNER), --id (a conversation id,
so re-sending the same conversation adds only new turns), --date (when it
happened), --scope (a project directory).

`context` and `recall` print plain text by default and JSON with --json.
"""
import argparse
import json
import os
import sys


def _read_messages(path):
    raw = (open(path, encoding="utf-8").read() if path and path != "-"
           else sys.stdin.read())
    raw = raw.strip()
    if not raw:
        return []
    if raw.startswith("["):
        msgs = json.loads(raw)
    else:
        msgs = [json.loads(l) for l in raw.splitlines() if l.strip()]
    out = []
    for m in msgs:
        role = str(m.get("role", "user")).lower()
        role = "assistant" if role in ("assistant", "ai", "model", "bot") else "user"
        content = m.get("content")
        if isinstance(content, list):          # [{"type": "text", "text": ...}]
            content = " ".join(c.get("text", "") for c in content
                               if isinstance(c, dict))
        if content:
            out.append({"role": role, "content": str(content)})
    return out


def _line(f):
    from memory_api import _render_fact
    return "- " + _render_fact(f)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sourcedrecall-memory",
                                 description="Use the memory from a terminal.")
    ap.add_argument("command", choices=["show", "path", "forget", "confirm",
                                        "context", "recall", "ingest"])
    ap.add_argument("arg", nargs="*", help="a fact id, a question, or a file")
    ap.add_argument("--owner", default=os.environ.get("SOURCEDRECALL_OWNER"))
    ap.add_argument("--id", dest="conv_id")
    ap.add_argument("--date")
    ap.add_argument("--scope")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.command in ("show", "path", "forget", "confirm"):
        os.environ.setdefault("RG_NLI", "0")   # no model needed to list facts
    from sourcedrecall.paths import default_memory_dir
    d = default_memory_dir()
    from sourcedrecall import profile_memory as pm
    arg = " ".join(a.arg).strip()

    if a.command == "path":
        print(d)
        print(os.path.join(d, "MEMORY.md"))
        return 0
    if a.command == "show":
        path = pm.export_markdown()
        print(open(path, encoding="utf-8").read())
        return 0
    if a.command == "context":
        out = pm.profile_context(arg or None, scope=a.scope)
        print(json.dumps(out, indent=2) if a.json else out["block"])
        return 0
    if a.command == "recall":
        if not arg:
            ap.error("recall needs a question")
        out = pm.profile_recall(arg, scope=a.scope)
        if a.json:
            print(json.dumps(out, indent=2, default=str))
        elif out.get("found"):
            for f in out.get("ranked") or []:
                print(_line(f))
        elif out.get("related"):
            print("Nothing stored is known to answer this. Closest things said:")
            for f in out["related"]:
                print(_line(f))
        else:
            print("Nothing stored about this.")
        return 0
    if a.command == "ingest":
        msgs = _read_messages(arg or None)
        if not msgs:
            print("nothing to store", file=sys.stderr)
            return 1
        out = pm.profile_ingest(msgs, conversation_id=a.conv_id,
                                owner_name=a.owner, date=a.date, scope=a.scope)
        print(json.dumps(out, indent=2) if a.json else
              f"stored {out['facts']} new facts from {out['turns']} messages "
              f"(conversation {out['conversation_id']})")
        return 0
    if not arg:
        ap.error(f"{a.command} needs a fact id (shown as `id` in `show`)")
    out = (pm.profile_forget if a.command == "forget" else pm.profile_confirm)(arg)
    print(json.dumps(out, indent=2))
    return 0 if not out.get("error") else 1


if __name__ == "__main__":
    sys.exit(main())
