"""Build a self-contained sourcedrecall wheel (2026-10-04).

    python tools/build_wheel.py            # -> server/dist/sourcedrecall-<v>-py3-none-any.whl

The server imports its memory code as flat modules from experiments/p2 and
the rgx package from the repository checkout. A wheel cannot rely on a
checkout, so this copies exactly the modules the server imports (found by
walking its imports) into server/sourcedrecall/_core/, builds the wheel, and
removes the copy again. At run time the path bridges use the checkout when
there is one and _core otherwise.
"""
import ast
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P2 = os.path.join(ROOT, "experiments", "p2")
PKG = os.path.join(ROOT, "server", "sourcedrecall")
CORE = os.path.join(PKG, "_core")


def _imports(path):
    tree = ast.parse(open(path, encoding="utf-8").read())
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            out.add(n.module.split(".")[0])
    return out


def closure():
    local = {f[:-3]: os.path.join(P2, f) for f in os.listdir(P2)
             if f.endswith(".py") and not f.startswith("test_")}
    todo = [os.path.join(PKG, f) for f in os.listdir(PKG) if f.endswith(".py")]
    todo += [os.path.join(ROOT, "rgx", f) for f in os.listdir(os.path.join(ROOT, "rgx"))
             if f.endswith(".py") and not f.startswith("test_")]
    seen = set()
    while todo:
        for m in _imports(todo.pop()):
            if m in local and m not in seen:
                seen.add(m)
                todo.append(local[m])
    return sorted(seen), local


def main():
    mods, local = closure()
    shutil.rmtree(CORE, ignore_errors=True)
    os.makedirs(os.path.join(CORE, "rgx"))
    for m in mods:
        shutil.copy2(local[m], os.path.join(CORE, m + ".py"))
    for f in os.listdir(os.path.join(ROOT, "rgx")):
        if f.endswith(".py") and not f.startswith("test_"):
            shutil.copy2(os.path.join(ROOT, "rgx", f), os.path.join(CORE, "rgx", f))
    # 2026-10-05: the PyTorch-free parser runtime (tools/stanza_ort)
    shutil.copytree(os.path.join(ROOT, "stanza_ort"), os.path.join(CORE, "stanza_ort"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    print(f"_core: {len(mods)} modules from experiments/p2 + rgx + stanza_ort")
    try:
        subprocess.run([sys.executable, "-m", "build", "--wheel", "--outdir",
                        os.path.join(ROOT, "server", "dist"),
                        os.path.join(ROOT, "server")], check=True)
    finally:
        shutil.rmtree(CORE, ignore_errors=True)


if __name__ == "__main__":
    main()
