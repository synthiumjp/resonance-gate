"""Locate the rg substrate and put its flat modules on sys.path. The rg-1.1
substrate is a set of numpy-only flat modules (substrate/, gate/, encoder/);
the server imports them from the repo checkout. RG_ROOT overrides the repo
root (defaults to three parents up from this file). mouth/ is deliberately
NOT added — the server contains no language model."""

import os
import sys

RG_ROOT = os.environ.get(
    "RG_ROOT",
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

for _p in (RG_ROOT, f"{RG_ROOT}/substrate", f"{RG_ROOT}/gate",
           f"{RG_ROOT}/encoder"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Embeddings must come from the local model cache only — a memory server that
# stores facts must never phone home. If the MiniLM encoder is not cached,
# a novel write fails loudly rather than downloading.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
