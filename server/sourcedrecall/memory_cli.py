"""sourcedrecall-memory: use the memory from a terminal, a script, or any
agent or model -- no MCP client needed.

    sourcedrecall-memory show                 print the memory (and rewrite MEMORY.md)
    sourcedrecall-memory path                 where the memory and MEMORY.md live
    sourcedrecall-memory forget <id>          remove a fact
    sourcedrecall-memory confirm <id>         mark a fact as confirmed
    sourcedrecall-memory context [question]   the text to put in any model's prompt
    sourcedrecall-memory recall <question>    what is stored about a question
    sourcedrecall-memory history <question>   search past coding sessions in this
                                              project (--all: every project)
    sourcedrecall-memory ingest [file]        store a conversation
    sourcedrecall-memory view [--port N]      browse it at http://127.0.0.1:7071
    sourcedrecall-memory notes-backfill       notes for conversations stored before notes were on

`ingest` reads JSON Lines from the file or stdin, one message per line:
    {"role": "user", "content": "I moved to Brunswick last week."}
    {"role": "assistant", "content": "Congratulations on the move!"}
A JSON array of the same objects also works. Options: --owner (the person
the memory is about; default SOURCEDRECALL_OWNER), --id (a conversation id,
so re-sending the same conversation adds only new turns), --date (when it
happened), --scope (a project directory).

`context` and `recall` print plain text by default and JSON with --json.
"""
import sourcedrecall.paths  # noqa: F401  (offline mode first)
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
    # 2026-10-14: conversations with an assistant (rgx RGX_ASSISTANT_CHAT)
    os.environ.setdefault("RGX_ASSISTANT_CHAT", "1")
    ap = argparse.ArgumentParser(prog="sourcedrecall-memory",
                                 description="Use the memory from a terminal.")
    ap.add_argument("command", choices=["show", "path", "forget", "confirm",
                                        "context", "recall", "check", "history", "ingest", "view",
                                        "notes-backfill", "status", "last", "rebuild"])
    ap.add_argument("arg", nargs="*", help="a fact id, a question, or a file")
    ap.add_argument("--owner", default=os.environ.get("SOURCEDRECALL_OWNER"))
    ap.add_argument("--id", dest="conv_id")
    ap.add_argument("--date")
    ap.add_argument("--scope")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--all", dest="all_projects", action="store_true",
                    help="history: search every project")
    ap.add_argument("--port", type=int, default=int(os.environ.get(
        "SOURCEDRECALL_BROWSER_PORT", "7071") or 7071))
    a = ap.parse_args(argv)
    if a.command in ("show", "path", "forget", "confirm", "status", "last"):
        os.environ.setdefault("RG_NLI", "0")   # no model needed to list facts
    from sourcedrecall.paths import default_memory_dir
    d = default_memory_dir()
    from sourcedrecall import profile_memory as pm
    arg = " ".join(a.arg).strip()

    if a.command == "path":
        print(d)
        print(os.path.join(d, "MEMORY.md"))
        return 0
    if a.command == "status":
        st = pm.memory_status()
        if a.json:
            print(json.dumps(st, indent=2))
            return 0
        ok = st["parser"] and all(st["models"].values()) and st["models"]
        print("models: " + ("ready" if ok else "missing -- run sourcedrecall-setup"))
        print(f"memory: {st['conversations']} conversations, {st['messages']} messages"
              + (f", last stored {st['last_stored']}" if st["last_stored"] else ""))
        print(f"folder: {st['memory_folder']}")
        print("notes model: " + ("installed" if st["notes_model"] else "not installed (optional)"))
        if st.get("error"):
            print("problem: " + st["error"])
        return 0 if ok and not st.get("error") else 1
    if a.command == "last":
        rec = pm.last_block()
        if not rec:
            print("Nothing has been handed to an agent yet.")
            return 0
        if a.json:
            print(json.dumps(rec, indent=2))
            return 0
        q = rec.get("question") or "(the summary at session start)"
        print(f"{rec['time']}  {q}  -- {rec['characters']} characters, about "
              f"{rec['tokens_about']} tokens\n")
        print(rec["block"])
        return 0
    if a.command == "rebuild":
        # 2026-10-14: the stored conversations read again with the current
        # parser (after an update that changes what it takes from a message)
        out = pm.profile_rebuild(a.owner)
        print(f"read {out['conversations']} conversations again; the old summaries are in "
              f"{out['backup'] or '(none)'}")
        return 0
    if a.command == "notes-backfill":
        n = pm.notes_backfill(a.owner)
        print(f"notes written for {n} stored conversation(s)")
        return 0
    if a.command == "show":
        path = pm.export_markdown()
        print(open(path, encoding="utf-8").read())
        return 0
    if a.command == "view":
        import http.server
        from sourcedrecall.browser import make_handler, new_token
        token = new_token()
        try:
            httpd = http.server.HTTPServer(("127.0.0.1", a.port), make_handler(None, token))
        except OSError:
            # the MCP server already serves it on this port: its address
            from sourcedrecall.browser import url_file
            try:
                print("memory at " + open(url_file()).read().strip())
                return 0
            except OSError:
                raise
        print(f"memory at http://127.0.0.1:{a.port}/?t={token}  (Ctrl-C to stop)", flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
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
    if a.command == "history":
        if not arg:
            ap.error("history needs a question, e.g. \"how did we fix the login test\"")
        out = pm.profile_history(arg, scope=a.scope, all_projects=a.all_projects, records=3)
        if a.json:
            print(json.dumps(out, indent=2, default=str))
            return 0
        if not out["results"]:
            print(f"Nothing in the coding history of {out['project']} matches this.")
        for r in out["results"]:
            where = f" {r['project']}" if a.all_projects and r.get("project") else ""
            print(f"[{r.get('date') or '?'}]{where} {r['kind']} ({r['id']})")
            print("  " + "\n  ".join(r["text"].splitlines()) + "\n")
        return 0
    if a.command == "check":
        if not arg:
            ap.error("check needs a claim, e.g. \"The user lives in Fitzroy\"")
        out = pm.profile_check(arg, scope=a.scope)
        if a.json:
            print(json.dumps(out, indent=2, default=str))
            return 0
        head = out["verdict"].replace("_", " ")
        if out.get("since"):
            head += f" ({out['since']})"
        print(head)
        for e in out["evidence"]:
            quote = e.get("said") or e.get("fact") or ""
            print(f"- [{e.get('date') or '?'}] {e.get('status')}: \"{quote}\"")
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
