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
    ("triple-store encoder", "sentence-transformers/all-MiniLM-L6-v2"),
]
from sourcedrecall._bridge import code_roots as _code_roots
_P2 = _code_roots()[1]


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


def main(argv=None):
    t0 = time.time()
    print("sourcedrecall setup: downloading the models the server uses.\n"
          "This is the only step that touches the network.\n")

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
