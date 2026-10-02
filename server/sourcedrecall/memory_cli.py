"""sourcedrecall-memory: look at and edit the memory from a terminal.

    sourcedrecall-memory show            print the memory (and rewrite MEMORY.md)
    sourcedrecall-memory path            where the memory and MEMORY.md live
    sourcedrecall-memory forget <id>     remove a fact
    sourcedrecall-memory confirm <id>    mark a fact as confirmed
"""
import argparse
import json
import os
import sys


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sourcedrecall-memory",
                                 description="Look at and edit the memory.")
    ap.add_argument("command", choices=["show", "path", "forget", "confirm"])
    ap.add_argument("fact_id", nargs="?")
    a = ap.parse_args(argv)
    os.environ.setdefault("RG_NLI", "0")      # no model needed to list facts
    from sourcedrecall.paths import default_memory_dir
    d = default_memory_dir()
    from sourcedrecall import profile_memory as pm
    if a.command == "path":
        print(d)
        print(os.path.join(d, "MEMORY.md"))
        return 0
    if a.command == "show":
        path = pm.export_markdown()
        print(open(path, encoding="utf-8").read())
        return 0
    if not a.fact_id:
        ap.error(f"{a.command} needs a fact id (shown as `id` in `show`)")
    out = (pm.profile_forget if a.command == "forget" else pm.profile_confirm)(a.fact_id)
    print(json.dumps(out, indent=2))
    return 0 if not out.get("error") else 1


if __name__ == "__main__":
    sys.exit(main())
