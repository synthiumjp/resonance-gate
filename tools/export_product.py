"""Export the product repository from this research repository (2026-10-14).

The public repository (synthiumjp/sourcedrecall) holds only the product:
the server, the parser rules and runtime, the plugin, the memory modules,
their tests, the product docs and the benchmark files the docs cite. This
writes that tree from a checkout of this repository, so development stays
here and the export is rerun for each release.

    python tools/export_product.py SRC KEEP_LIST DEST

SRC is a checkout (or `git archive` of one), KEEP_LIST a file of further
paths to keep (bench/, docs/, tools/; one per line), DEST an empty or
missing directory. Changes made on the way:

- the memory modules move from experiments/p2/ to core/ (only the ones the
  server imports, found by walking its imports as tools/build_wheel.py
  does), with the tests whose imports stay inside the product;
- the HaluMem harness moves from experiments/p2/halumem_official/ to
  bench/halumem/harness/;
- paths written into benchmark results (the machines the runs were made
  on) are replaced by <repo> and <work>;
- a few sentences that point at the research repository are removed.

It stops with a list if any kept text still mentions experiments/p2, a
home directory or an email address.
"""
import ast
import os
import re
import shutil
import sys

SRC, KEEP, DEST = sys.argv[1:4]
P2 = os.path.join(SRC, "experiments", "p2")

TOP_FILES = ["README.md", "NOTICE", "LICENSE", "SECURITY.md", "CITATION.cff", ".gitignore"]
TOP_DIRS = [".claude-plugin", "plugins", "server", "rgx", "stanza_ort", ".github"]
# research tools whose tests `pytest tools` would otherwise collect
DROP = {"tools/check_judged.py", "tools/test_check_judged.py", "tools/export_product.py",
        "tools/stanza_ort/PROGRESS.md", "tools/distil/deixis_parse.py", "tools/distil/tsent.py",
        "server/sourcedrecall/_core"}


def imports(path):
    tree = ast.parse(open(path, encoding="utf-8").read())
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            out.add(n.module.split(".")[0])
    return out


def product_modules():
    local = {f[:-3]: os.path.join(P2, f) for f in os.listdir(P2)
             if f.endswith(".py") and not f.startswith("test_")}
    pkg = os.path.join(SRC, "server", "sourcedrecall")
    todo = [os.path.join(pkg, f) for f in os.listdir(pkg) if f.endswith(".py")]
    todo += [os.path.join(SRC, "rgx", f) for f in os.listdir(os.path.join(SRC, "rgx"))
             if f.endswith(".py")]
    seen = set()
    while todo:
        for m in imports(todo.pop()):
            if m in local and m not in seen:
                seen.add(m)
                todo.append(local[m])
    return seen, set(local)


def product_tests(mods, local):
    research_dirs = {"substrate", "gate", "encoder", "mouth", "coref", "e5", "instruments",
                     "halumem_official", "llms"}
    keep = []
    for f in sorted(os.listdir(P2)):
        if f.startswith("test_") and f.endswith(".py"):
            im = imports(os.path.join(P2, f))
            if (im & local) <= mods and not (im & research_dirs):
                keep.append(f)
    return keep


def copy(rel_src, rel_dst=None):
    s = os.path.join(SRC, rel_src)
    d = os.path.join(DEST, rel_dst or rel_src)
    os.makedirs(os.path.dirname(d), exist_ok=True)
    shutil.copy2(s, d)


def walk(rel):
    base = os.path.join(SRC, rel)
    if os.path.isfile(base):
        yield rel
        return
    for dp, dns, fns in os.walk(base):
        dns[:] = [d for d in dns if d not in ("__pycache__", ".pytest_cache")]
        for f in fns:
            if not f.endswith(".pyc"):
                yield os.path.relpath(os.path.join(dp, f), SRC)


def dropped(rel):
    return any(rel == d or rel.startswith(d + "/") for d in DROP)


# text rewrites, in order; applied to every kept text file
REWRITES = [
    ('os.path.join(repo, "experiments", "p2")', 'os.path.join(repo, "core")'),
    ('"experiments", "p2"', '"core"'),
    ("'experiments', 'p2'", "'core'"),
    ("experiments/p2/halumem_official", "bench/halumem/harness"),
    ("experiments/p2", "core"),
]
SCRUB = [
    (re.compile(r"/Users/[A-Za-z0-9_.-]+/jpwork/[A-Za-z0-9_.-]+"), "<repo>"),
    (re.compile(r"/Users/[A-Za-z0-9_.-]+/jpwork"), "<work>"),
    (re.compile(r"/Users/[A-Za-z0-9_.-]+"), "<home>"),
    (re.compile(r"/home/jp/rg"), "<repo>"),
    (re.compile(r"/home/jp"), "<home>"),
]
CUT_LINES = [
    "- This repository also holds the research the product came from (`experiments/`, `notebook.md`).\n",
]
CUT_TEXT = [
    (" The research notebook (`notebook.md`)\nhas the details behind each change.", ""),
    (" (notebook e323)", ""),
]
# files moved one directory up (experiments/p2 -> core): their own path to
# the repository root is one dirname shorter
UP_ONE = [("os.path.dirname(os.path.dirname(_HERE))", "os.path.dirname(_HERE)")]
HARNESS_FIX = [("_P2 = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))",
                "_P2 = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(\n"
                "    os.path.dirname(os.path.realpath(__file__))))), \"core\")")]

TEXT = (".py", ".md", ".sh", ".txt", ".json", ".jsonl", ".toml", ".yml", ".yaml", ".cff",
        ".log", ".env", "")


def rewrite(path, extra=()):
    if not path.endswith(TEXT) or os.path.basename(path) == "LICENSE":
        return
    try:
        s = open(path, encoding="utf-8").read()
    except UnicodeDecodeError:
        return
    t = s
    for a, b in list(extra) + REWRITES:
        t = t.replace(a, b)
    for rx, b in SCRUB:
        t = rx.sub(b, t)
    for line in CUT_LINES:
        t = t.replace(line, "")
    for a, b in CUT_TEXT:
        t = t.replace(a, b)
    if t != s:
        open(path, "w", encoding="utf-8").write(t)


def main():
    if os.path.exists(DEST) and os.listdir(DEST):
        sys.exit(f"{DEST} is not empty")
    mods, local = product_modules()
    tests = product_tests(mods, local)
    moved = {}
    for m in sorted(mods):
        moved[f"experiments/p2/{m}.py"] = f"core/{m}.py"
    for t in tests:
        moved[f"experiments/p2/{t}"] = f"core/{t}"
    for rel in walk("experiments/p2/halumem_official"):
        moved[rel] = rel.replace("experiments/p2/halumem_official", "bench/halumem/harness")
    for a, b in moved.items():
        copy(a, b)
    rels = list(TOP_FILES)
    for d in TOP_DIRS:
        rels += list(walk(d))
    for line in open(KEEP, encoding="utf-8"):
        p = line.strip()
        if p and not p.startswith("#") and not p.startswith("experiments/"):
            rels += list(walk(p))
    n = 0
    for rel in sorted(set(rels)):
        if dropped(rel) or not os.path.exists(os.path.join(SRC, rel)):
            continue
        copy(rel)
        n += 1
    # a conftest for the product tests only (the research one adds the
    # substrate directories)
    open(os.path.join(DEST, "conftest.py"), "w").write(
        "import os\nimport sys\n\nROOT = os.path.dirname(os.path.abspath(__file__))\n"
        "for p in (ROOT, os.path.join(ROOT, \"core\")):\n"
        "    if p not in sys.path:\n        sys.path.insert(0, p)\n")
    for dp, _, fns in os.walk(DEST):
        for f in fns:
            path = os.path.join(dp, f)
            rel = os.path.relpath(path, DEST)
            extra = []
            if rel.startswith("core/"):
                extra = UP_ONE
            if rel == "bench/halumem/harness/eval_sdr.py":
                extra = HARNESS_FIX
            rewrite(path, extra)
    left = []
    rx = re.compile(r"experiments/p2|experiments\", \"p2|/Users/|/home/jp|hotmail|chrismarmo")
    for dp, _, fns in os.walk(DEST):
        for f in fns:
            path = os.path.join(dp, f)
            try:
                for i, line in enumerate(open(path, encoding="utf-8"), 1):
                    if rx.search(line):
                        left.append(f"{os.path.relpath(path, DEST)}:{i}: {line.strip()[:120]}")
            except UnicodeDecodeError:
                pass
    print(f"exported {n} files + {len(moved)} moved ({len(mods)} memory modules, "
          f"{len(tests)} tests) to {DEST}")
    if left:
        print(f"{len(left)} lines still need a look:")
        print("\n".join(left[:200]))
        sys.exit(1)


if __name__ == "__main__":
    main()
