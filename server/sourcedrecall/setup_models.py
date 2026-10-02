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
HF_MODELS = [
    ("retrieval embedder", "BAAI/bge-small-en-v1.5", "bi"),
    ("retrieval re-ranker", "cross-encoder/ms-marco-MiniLM-L6-v2", "ce"),
    ("conflict checker (NLI)", "cross-encoder/nli-deberta-v3-xsmall", "nli"),
    ("triple-store encoder", "sentence-transformers/all-MiniLM-L6-v2", "bi"),
]


def _du(path):
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def _mb(n):
    return f"{n / 1e6:,.0f} MB"


def main(argv=None):
    t0 = time.time()
    print("sourcedrecall setup: downloading the models the server uses.\n"
          "This is the only step that touches the network.\n")

    print(f"[1/{1 + len(HF_MODELS)}] English parser (Stanza: {STANZA_PROCESSORS})")
    import stanza
    stanza.download("en", processors=STANZA_PROCESSORS, verbose=False)
    from stanza.resources.common import DEFAULT_MODEL_DIR
    sdir = os.environ.get("STANZA_RESOURCES_DIR", DEFAULT_MODEL_DIR)
    print(f"      -> {sdir} ({_mb(_du(sdir))})")

    from huggingface_hub import constants as hfc
    for i, (what, name, kind) in enumerate(HF_MODELS, start=2):
        print(f"[{i}/{1 + len(HF_MODELS)}] {what}: {name}")
        if kind == "bi":
            from sentence_transformers import SentenceTransformer
            SentenceTransformer(name, device="cpu")
        elif kind == "ce":
            from sentence_transformers import CrossEncoder
            CrossEncoder(name, device="cpu")
        else:
            from transformers import pipeline
            pipeline("text-classification", model=name, device=-1)
    print(f"      -> {hfc.HF_HUB_CACHE} ({_mb(_du(hfc.HF_HUB_CACHE))} in that cache)")

    print(f"\nDone in {time.time() - t0:.0f} s. The server will now run fully "
          "offline.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
