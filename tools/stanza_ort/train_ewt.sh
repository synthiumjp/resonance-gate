#!/bin/bash
# The sourcedrecall English parser's POS tagger and dependency parser
# (2026-10-13 to 15): trained on UD English-EWT alone (CC BY-SA 4.0; v2.18
# used) with the GloVe vectors Stanza packages for English (glove.pt, 100k
# words x 100 dims; GloVe is under the Public Domain Dedication and
# License), no character language model, on CPU with Stanza 1.14.0's own
# training scripts. The dependency data is retagged by this POS model, so
# no model trained on other data is involved. The tokenizer, multi-word
# token and lemma models are Stanza's EWT-only ones (en/tokenize/ewt.pt,
# en/mwt/ewt.pt, en/lemma/ewt_nocharlm.pt).
#
#   UDBASE=<dir holding UD_English-EWT> GLOVE=<stanza en/pretrain/glove.pt> \
#     PY=<python with stanza==1.14.0 and torch> bash train_ewt.sh <work dir>
#
# Results here (UD EWT test, gold words, head repair on): UPOS 96.41, UAS
# 91.05, LAS 88.83 (Stanza's own ewt_nocharlm models 96.68 / 91.25 / 88.77).
# CPU only: the parser took about 10 hours (best dev score at step 17,000).
# Then convert (STANZA_PACKAGES=ours convert.py) and check (parity.py).
set -u
cd "$1"
: "${UDBASE:?}" "${GLOVE:?}" "${PY:?}"
export UDBASE
echo "== ewt train $(date)"
$PY -m stanza.utils.datasets.prepare_pos_treebank UD_English-EWT > prep_pos.log 2>&1 || { echo "prep pos failed"; exit 1; }
$PY -m stanza.utils.training.run_pos UD_English-EWT --no_charlm --wordvec_pretrain_file "$GLOVE" \
    --save_name en_ewt_glove_nocharlm_tagger.pt --device cpu --max_steps 20000 --force > pos.log 2>&1 || { echo "pos failed"; exit 1; }
T=saved_models/pos/en_ewt_glove_nocharlm_tagger.pt
$PY -m stanza.utils.datasets.prepare_depparse_treebank UD_English-EWT --predicted --tagger_model $T \
    --wordvec_pretrain_file "$GLOVE" --no_charlm --no_download_tagger > prep_dep.log 2>&1 || { echo "prep dep failed"; exit 1; }
$PY -m stanza.utils.training.run_depparse UD_English-EWT --no_charlm --wordvec_pretrain_file "$GLOVE" \
    --save_name en_ewt_glove_nocharlm_parser.pt --device cpu --max_steps 30000 --force > dep.log 2>&1 || { echo "dep failed"; exit 1; }
# Training saves resolve_head_constraints=False in the model's config, so
# Stanza's pipeline would skip the head repair it does for its own models
# (where the key is absent: on); stanza_ort always repairs. Removing the key
# makes Stanza on PyTorch and the converted models parse identically
# (7,755 texts, parity.py).
$PY - <<'EOF'
import torch
p = "saved_models/depparse/en_ewt_glove_nocharlm_parser.pt"
m = torch.load(p, map_location="cpu", weights_only=False)
m["config"].pop("resolve_head_constraints", None)
torch.save(m, "en_ewt_glove_nocharlm_parser_rhc.pt")
EOF
grep -iE "score" pos.log dep.log | tail -4
echo "== ewt train done $(date)"
