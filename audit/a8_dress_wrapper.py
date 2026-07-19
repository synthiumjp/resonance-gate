"""A8: run the committed dress rehearsal UNMODIFIED, but with the embedding
disk cache redirected to scratch first — dress_rehearsal's checker path can
embed novel LLM-extracted strings, which would rewrite encoder/.emb_cache.npz
(a frozen-dir file). Usage mirrors dress_rehearsal.py:

  python audit/a8_dress_wrapper.py [--quick] [--seed N] --out PATH
"""

import sys

import _common
_common.patch_cache()

import dress_rehearsal

if __name__ == "__main__":
    sys.argv[0] = "dress_rehearsal.py"
    dress_rehearsal.main()
