"""One-time model download for sourcedrecall.

    sourcedrecall-setup

The server runs OFFLINE: it sets HF_HUB_OFFLINE=1 at import, and the parser
never fetches anything at runtime. That is the privacy property -- nothing
leaves the machine -- but it also means a fresh install has no models until
something downloads them. This is that something: the ONLY place network
access is allowed, run once, explicitly, and it says what it fetched, how
big it is and where it went.

2026-10-02: written after reading the README against a genuinely fresh
machine. The first README rewrite claimed the models "download on first
use"; with offline mode forced, they never would have.
"""
import os
import sys
import time

# Network allowed for THIS process only, and before any HF import reads it.
os.environ["HF_HUB_OFFLINE"] = "0"
os.environ["TRANSFORMERS_OFFLINE"] = "0"

# (what, size guide, loader) -- every model the server can load
STANZA_PROCESSORS = "tokenize,pos,lemma,depparse"   # rgx's pipeline
# 2026-10-02: each model's official ONNX export, stored with fp16 weights
# (experiments/p2/ort_models.py): half the disk, identical results, and no
# transformers / sentence-transformers.
HF_MODELS = [
    ("retrieval embedder", "BAAI/bge-small-en-v1.5"),
    ("retrieval re-ranker", "cross-encoder/ms-marco-MiniLM-L6-v2"),
    ("conflict checker (NLI)", "cross-encoder/nli-deberta-v3-xsmall"),
]
# only the rg-1.1 triple tools use it, and they are off by default
# (SOURCEDRECALL_LEGACY_TOOLS=1, mcp_server.py)
if os.environ.get("SOURCEDRECALL_LEGACY_TOOLS") == "1":
    HF_MODELS.append(("triple-store encoder", "sentence-transformers/all-MiniLM-L6-v2"))
from sourcedrecall._bridge import code_roots as _code_roots
_P2 = _code_roots()[1]


# 2026-10-05: the PyTorch-free parser. Its models are Stanza 1.14.0's English
# models converted once by tools/stanza_ort/convert.py and packed as a
# .tar.gz; where that archive is published is set here at release time.
# Until then setup downloads Stanza's own models (and PyTorch runs them), or
# SOURCEDRECALL_PARSER_ARCHIVE names an archive (path or URL) to install.
PARSER_ARCHIVE = ("https://huggingface.co/synthiumjp/sourcedrecall-parser-en/resolve/main/"
                  "sourcedrecall-parser-en-stanza1.14.0.tar.gz")
PARSER_SHA256 = "921281ed755e8a4454cce27df56e18557123920e1df4b02443cade72e0e2f105"


# 2026-10-06: the optional in-process notes model (notes.py): Qwen3-0.6B
# trained to write the user's lasting facts, int4 ONNX for onnxruntime-genai.
# Set at release time; SOURCEDRECALL_NOTES_ARCHIVE overrides.
NOTES_ARCHIVE = None
NOTES_SHA256 = None


def install_parser_archive(src, sha256=None):
    """Download (if a URL) or copy the parser model archive, check its
    sha256 when one is given, and unpack it into paths.parser_models_dir()."""
    from sourcedrecall.paths import parser_models_dir
    return install_archive(src, sha256, parser_models_dir(), "config.json", "parser")


def install_archive(src, sha256, dest, marker, what):
    """The same for any model archive whose top folder holds `marker`."""
    import hashlib
    import shutil
    import tarfile
    import tempfile
    import urllib.request
    tmp = tempfile.mkdtemp(prefix=f"sourcedrecall-{what}-")
    try:
        path = os.path.join(tmp, "models.tar.gz")
        if src.startswith(("http://", "https://")):
            urllib.request.urlretrieve(src, path)
        else:
            shutil.copyfile(src, path)
        if sha256:
            h = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            if h.hexdigest() != sha256.lower():
                raise RuntimeError(f"{what} model archive: sha256 does not match")
        out = os.path.join(tmp, "out")
        with tarfile.open(path) as t:
            for m in t.getmembers():
                if m.name.startswith(("/", "..")) or ".." in m.name.split("/"):
                    raise RuntimeError(f"{what} model archive: unsafe path " + m.name)
            try:
                t.extractall(out, filter="data")      # Python 3.12+: no links out, no odd modes
            except TypeError:
                t.extractall(out)
        # the archive holds the marker file at its top or in one folder
        top = out
        if not os.path.exists(os.path.join(top, marker)):
            subs = [os.path.join(out, x) for x in os.listdir(out)]
            top = next((x for x in subs if os.path.exists(os.path.join(x, marker))), None)
            if top is None:
                raise RuntimeError(f"{what} model archive: no {marker}")
        if os.path.exists(dest):
            shutil.rmtree(dest)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.move(top, dest)
        return dest
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _du(path):
    """Bytes actually on disk. Skips symlinks: the HF cache links every
    snapshot file to a blob, and following both reported 2.8 GB for an
    0.9 GB cache (second new-user test)."""
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            fp = os.path.join(root, f)
            if os.path.islink(fp):
                continue
            try:
                total += os.path.getsize(fp)
            except OSError:
                pass
    return total


def _mb(n):
    return f"{n / 1e6:,.0f} MB"


def install_notes():
    """`sourcedrecall-setup --notes`: install the notes model, which turns
    notes on (about 0.5 GB; needs pip install 'sourcedrecall[notes]')."""
    try:
        import onnxruntime_genai  # noqa: F401
    except ImportError:
        print("Notes need onnxruntime-genai: pip install 'sourcedrecall[notes]'")
        return 1
    src = os.environ.get("SOURCEDRECALL_NOTES_ARCHIVE") or NOTES_ARCHIVE
    if not src:
        print("No notes model has been published yet.")
        return 1
    from sourcedrecall.paths import notes_models_dir
    sha = (os.environ.get("SOURCEDRECALL_NOTES_SHA256")
           or (NOTES_SHA256 if src == NOTES_ARCHIVE else None))
    print("Notes model (writes short notes of what you said, in this process,"
          " no server) -- ~0.5 GB", flush=True)
    d = install_archive(src, sha, notes_models_dir(), "genai_config.json", "notes")
    print(f"      -> {d} ({_mb(_du(d))})\nNotes are on. To turn them off: "
          "SOURCEDRECALL_NOTES=off, or delete that folder.")
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--notes" in argv:
        return install_notes()
    t0 = time.time()
    print("sourcedrecall setup: downloading the models the server uses.\n"
          "This is the only step that touches the network.\n")

    archive = os.environ.get("SOURCEDRECALL_PARSER_ARCHIVE") or PARSER_ARCHIVE
    done = False
    if archive and os.environ.get("RGX_PARSER", "").lower() != "stanza":
        print(f"[1/{1 + len(HF_MODELS)}] English parser (Stanza's models on ONNX "
              "Runtime, no PyTorch) -- ~335 MB, the slowest step", flush=True)
        try:
            sha = (os.environ.get("SOURCEDRECALL_PARSER_SHA256")
                   or (PARSER_SHA256 if archive == PARSER_ARCHIVE else None))
            d = install_parser_archive(archive, sha)
            print(f"      -> {d} ({_mb(_du(d))})")
            done = True
        except Exception as e:
            print(f"      -> could not install ({e}); trying Stanza with PyTorch")
    if not done:
        try:
            import stanza  # noqa: F401
        except ImportError:
            print("\nThe parser models could not be installed, and Stanza with "
                  "PyTorch (the fallback) is not installed either. Check the "
                  "network and run sourcedrecall-setup again, or install the "
                  "fallback: pip install 'sourcedrecall[stanza]' (on Linux, "
                  "first: pip install torch --index-url "
                  "https://download.pytorch.org/whl/cpu).")
            return 1
        print(f"[1/{1 + len(HF_MODELS)}] English parser (Stanza: {STANZA_PROCESSORS})"
              " -- ~320 MB, the slowest step", flush=True)
        import stanza
        stanza.download("en", processors=STANZA_PROCESSORS)
        from stanza.resources.common import DEFAULT_MODEL_DIR
        sdir = os.environ.get("STANZA_RESOURCES_DIR", DEFAULT_MODEL_DIR)
        print(f"      -> {sdir} ({_mb(_du(sdir))})")

    if _P2 not in sys.path:
        sys.path.insert(0, _P2)
    import ort_models
    for i, (what, name) in enumerate(HF_MODELS, start=2):
        print(f"[{i}/{1 + len(HF_MODELS)}] {what}: {name}", flush=True)
        ort_models.ensure(name)
    # Size of THESE models only
    ours = sum(_du(ort_models.model_dir(name)) for _w, name in HF_MODELS)
    root = os.path.dirname(ort_models.model_dir(HF_MODELS[0][1]))
    print(f"      -> {root} ({_mb(ours)} for these {len(HF_MODELS)} models)")

    # WordNet: what TYPE of thing a question asks for (tea is a beverage,
    # Leeds is a city). Optional -- without it those checks are skipped.
    print("[+] WordNet (answer types) -- ~11 MB", flush=True)
    try:
        import nltk
        nltk.download("wordnet", quiet=True)
        print("      -> done")
    except Exception as e:
        print(f"      -> skipped ({e.__class__.__name__}); answer types off")

    print(f"\nDone in {time.time() - t0:.0f} s. The server will now run fully "
          "offline.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
