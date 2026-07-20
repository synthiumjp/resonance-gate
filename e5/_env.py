"""E5 environment plumbing. The frozen dirs (substrate/, gate/, encoder/,
mouth/) and instruments/ are READ-ONLY in E5: before any Registry is built,
the embedding disk cache is redirected to e5/.emb_cache_e5.npz (seeded from
the committed encoder cache on first use, then committed with e5/ so E5
numbers are byte-reproducible without ever touching encoder/)."""

import os
import shutil
import sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (R, f"{R}/substrate", f"{R}/gate", f"{R}/encoder", f"{R}/mouth",
           f"{R}/instruments", f"{R}/e5"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

E5_CACHE = os.path.join(R, "e5", ".emb_cache_e5.npz")

# E5 seed families (disjoint from every dev seed logged in notebook entries
# 1-12, the three consumed confirmatory blocks 777/888/999, and the audit
# seeds). DEV drives pilot tuning + FOIL-v2 training; EVAL is run once by
# run_e51.py and never used for tuning.
SEED_DEV_CORPUS = 5551001
SEED_FOIL_TRAIN = 5551002
SEED_EVAL_CORPUS = 5552001
SEED_ASSIGN = 5552002
SEED_BOOT = 5552003
SEED_PERM = 5552004


def patch_cache():
    import e31_common
    if not os.path.exists(E5_CACHE):
        shutil.copy(os.path.join(R, "encoder", ".emb_cache.npz"), E5_CACHE)
    e31_common.CACHE_PATH = E5_CACHE
    return E5_CACHE
