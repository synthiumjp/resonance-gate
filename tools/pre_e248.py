#!/usr/bin/env python3
"""Pre-e248 renderer loader.

Commit cd34271 ("e248") fixed three rendering leaks: `retrieve.py:format_fact`
(the QA CONTEXT renderer -- never got the entry-244 "prefer the node's own
proposition text" treatment), `currency.py:mark_current` (the `supersedes`
list annotation), and `timeline.py:change_history` (the CHANGE HISTORY
section header). All three hunks are STRING-ONLY changes: none of them touch
which facts are selected, scored, or ordered (see notebook / handover for the
per-hunk audit). That means a harness comparing pre/post-e248 QA contexts can
retrieve ONCE against the current (post-e248) store and render the same fact
list two ways, rather than re-running ingestion against two different code
trees.

This module materialises the PRE-e248 (parent commit cd34271^) source of
those three files into a throwaway directory via `git show`, and imports them
under distinct module names (`pre_e248_currency`, `pre_e248_retrieve`,
`pre_e248_timeline`) so both the old and new implementations are live in the
same process. Their own sibling imports (`from wire import ...`, `from
propositions import ...`) resolve against the CURRENT experiments/p2 tree,
because wire.py/propositions.py are unchanged by e248 -- only the three files
above moved.

`old_format_fact` is exposed at module level (signature-compatible with
`retrieve.format_fact(d, owner=None)`) because that is the only one of the
three actually exercised by tools/context_diff.py: currency's and timeline's
e248 changes are gated behind flags (RG_SUPERSEDE / RG_TIMELINE) that the QA
context diff does not turn on. `old_mark_current` and `old_change_history`
are exposed too, for completeness / future use.

Usage:
    import pre_e248
    line = pre_e248.old_format_fact(node_dict, owner="Martin Mark")

    python3 tools/pre_e248.py     # self-check: prints old vs new rendering
                                   # of a node dict that has a "text" key
"""
import importlib.util
import os
import subprocess
import sys
import tempfile

REPO = "/home/jp/rg"
P2 = os.path.join(REPO, "experiments/p2")
PRE_REV = "cd34271^"          # the parent of e248 -- last commit before the fix

_FILES = ["currency.py", "retrieve.py", "timeline.py"]

_dest_dir = None               # populated by materialize(), memoised
_modules = {}                  # populated by load_all(), memoised


def materialize(dest_dir=None):
    """git-show the PRE_REV version of each file in _FILES into dest_dir
    (a fresh tempdir by default; memoised on repeat calls with no arg).
    Filenames match the originals on purpose -- their sibling imports
    (`from wire import ...`) only resolve correctly if P2 is ALSO on
    sys.path (see load_all()); this directory itself never needs to be on
    sys.path since each file is loaded by explicit path below."""
    global _dest_dir
    if dest_dir is None and _dest_dir is not None:
        return _dest_dir
    dest_dir = dest_dir or tempfile.mkdtemp(prefix="rg_pre_e248_")
    for fname in _FILES:
        rel = f"experiments/p2/{fname}"
        out = subprocess.run(
            ["git", "-C", REPO, "show", f"{PRE_REV}:{rel}"],
            capture_output=True, text=True, check=True)
        with open(os.path.join(dest_dir, fname), "w") as f:
            f.write(out.stdout)
    _dest_dir = dest_dir
    return dest_dir


def _load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def load_all(dest_dir=None):
    """Import the pre-e248 currency/retrieve/timeline modules under
    pre_e248_<name>, alongside (not instead of) the current ones. Returns
    {"currency": mod, "retrieve": mod, "timeline": mod}. Memoised."""
    if _modules:
        return _modules
    if P2 not in sys.path:
        sys.path.insert(0, P2)          # so `from wire import ...` etc. resolve
    dest_dir = materialize(dest_dir)
    for fname in _FILES:
        stem = fname[:-3]
        name = "pre_e248_" + stem
        _modules[stem] = _load_module(os.path.join(dest_dir, fname), name)
    return _modules


def _old_retrieve():
    return load_all()["retrieve"]


def old_format_fact(d, owner=None):
    """Pre-e248 `retrieve.format_fact` -- the QA-context line renderer
    before the entry-244 text fix. Never reads d["text"]; renders the bare
    `attr: value` atom (or, under RG_QA_PROPS=1, propositions.render)."""
    return _old_retrieve().format_fact(d, owner=owner)


def old_mark_current(nodes):
    """Pre-e248 `currency.mark_current` -- appends the retired node's bare
    VALUE to the winner's `supersedes` list, not its proposition text."""
    return load_all()["currency"].mark_current(nodes)


def old_change_history(mem, retrieved_facts):
    """Pre-e248 `timeline.change_history` -- always headers a chain with
    the raw `attr` key, even when every member carries full proposition
    text (the predicate-key leak entry 248 fixed)."""
    return load_all()["timeline"].change_history(mem, retrieved_facts)


if __name__ == "__main__":
    if P2 not in sys.path:
        sys.path.insert(0, P2)
    import retrieve as new_retrieve

    node = {
        "attr": "openness_to_exploring_new_experiences_such_as_action_games",
        "value": "a testament to martin mark's commitment to innovation",
        "text": "Martin Mark's openness to exploring new experiences such "
                "as action games demonstrates his commitment to innovation",
        "n_mentions": 2,
        "convs": {"c0": "2026-01-01"},
    }

    new_line = new_retrieve.format_fact(node)
    old_line = old_format_fact(node)

    print("dest dir      :", materialize())
    print("NEW format_fact:", new_line)
    print("OLD format_fact:", old_line)
    print()
    assert node["text"] in new_line, "new format_fact should use node['text']"
    assert node["text"] not in old_line, (
        "old format_fact should NOT use node['text'] -- if this fires, the "
        "materialised pre-e248 file is not actually pre-e248")
    assert "openness_to_exploring_new_experiences_such_as_action_games:" in old_line
    print("OK: pre-e248 format_fact ignores node['text'] and leaks the raw "
          "attr key; post-e248 format_fact prefers node['text']. The two "
          "renderers are demonstrably different on the same input.")
