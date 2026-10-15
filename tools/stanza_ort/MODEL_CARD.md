---
license: cc-by-sa-4.0
language:
- en
library_name: onnxruntime
tags:
- stanza
- dependency-parsing
- part-of-speech
- lemmatization
- onnx
- universal-dependencies
datasets:
- universal_dependencies
---

# sourcedrecall English parser models (UD English-EWT, ONNX)

An English tokenizer, multi-word token expander, part-of-speech tagger, lemmatizer and
dependency parser in the architecture of [Stanza](https://github.com/stanfordnlp/stanza)
1.14.0, trained only on openly licensed data and converted so they run on
[ONNX Runtime](https://onnxruntime.ai) and numpy without PyTorch.

They are used by [sourcedrecall](https://github.com/synthiumjp/sourcedrecall), a local
memory for AI assistants whose grammar rules read the user's messages through these
parses. Running them without PyTorch cuts its install by about 600 MB.

## What they were trained on

- Part-of-speech tagger and dependency parser: trained for sourcedrecall on
  [UD English-EWT](https://github.com/UniversalDependencies/UD_English-EWT) v2.18 alone
  (CC BY-SA 4.0), with the GloVe word vectors Stanza packages for English (100,000 words,
  100 dimensions; GloVe is under the Open Data Commons Public Domain Dedication and
  License), no character language model, using Stanza 1.14.0's training scripts
  (`tools/stanza_ort/train_ewt.sh` in the sourcedrecall repository). The parser's
  training data was tagged by this tagger.
- Tokenizer, multi-word token expander and lemmatizer: Stanza's own English EWT models
  (`tokenize/ewt`, `mwt/ewt`, `lemma/ewt_nocharlm`), trained by the Stanford NLP Group on
  UD English-EWT.

So every model here is trained on UD English-EWT and nothing else, and the archive
includes no data or vectors under a non-commercial licence. An earlier archive in this
repository (`sourcedrecall-parser-en-stanza1.14.0.tar.gz`, at commit 72e0cff) holds
Stanza's English "combined" models instead, which are partly trained on text under
non-commercial terms; sourcedrecall no longer uses it.

## Accuracy

UD English-EWT test set, gold tokenization (tagging and parsing only), every word:

| | UPOS | UAS | LAS |
|---|---|---|---|
| these models | 96.41 | 91.05 | 88.83 |
| Stanza's own EWT models without a character model | 96.68 | 91.25 | 88.77 |
| Stanza's default English "combined" models | 96.77 | 92.20 | 90.04 |

In sourcedrecall, the same code with these models and with Stanza's combined models
gave the same LoCoMo test score (854 of 1,307 questions; 44 questions only one got right,
44 only the other) and the same counts on its pasted-text sets (2026-10-15).

## Same parses as Stanza

The runtime that loads these files (`stanza_ort`, in the sourcedrecall repository) was
checked against Stanza 1.14.0 on PyTorch with the same models on 7,755 texts (246,425
words): every LoCoMo conversation turn, the sourcedrecall benchmark cases, its parser
test sentences, and long and unusual inputs (lists, code mixed with prose, emoji,
8,000-character messages). Every field of every word (text, upos, xpos, feats, lemma,
head, deprel, character offsets) and every sentence split was identical, one text at a
time and in batches of 64. Checked on macOS arm64.

The PyTorch files the archive was converted from are in `pytorch/` here, for that check
and for anyone who wants to use them with Stanza itself. The trained parser's saved
config has `resolve_head_constraints` removed: Stanza's training writes it as off, which
makes Stanza's pipeline skip the head repair it does for its own models.

## Files

`sourcedrecall-parser-en-ewt.tar.gz` unpacks to:

| file | what it is |
|---|---|
| `tok.onnx` | tokenizer and sentence splitter network |
| `pos.onnx`, `pos_char.onnx` | part-of-speech and morphological features tagger, its character model |
| `dep.onnx`, `dep_char.onnx` | dependency parser (arc and label scorers), its character model |
| `pretrain_emb.npy` | the word vectors the tagger and parser use |
| `lemma.npz`, `mwt.npz` | weights of the lemmatizer and multi-word token sequence models |
| `config.json` | vocabularies, model settings and the lemma dictionaries |
| `NOTICE` | where each part comes from and its licence |

sha256 of the archive: `3cde3a9b29b6da81e72ad3208874fcdbb1961df82130829d3b8f7dd01ef362b1`

## How they were made

`tools/stanza_ort/convert.py` in the sourcedrecall repository loads the models with
Stanza 1.14.0 (`STANZA_PACKAGES=ours`, `tools/stanza_ort/pkgs.py`) and exports each
network with `torch.onnx.export`; two layers were rewritten in exactly equivalent form
for export (`nn.Bilinear` as an einsum, a boolean identity mask from `arange`).
`tools/stanza_ort/parity.py` is the comparison above.

## Licence and credit

The model weights are released under CC BY-SA 4.0, the licence of the UD English-EWT
data they are trained on. The conversion code and the runtime are Apache-2.0, in the
sourcedrecall repository. The architecture, training code, and the tokenizer, multi-word
token and lemma models are Stanza's, by the Stanford NLP Group (Apache-2.0).

Peng Qi, Yuhao Zhang, Yuhui Zhang, Jason Bolton and Christopher D. Manning. 2020.
Stanza: A Python Natural Language Processing Toolkit for Many Human Languages.
In Proceedings of ACL 2020: System Demonstrations.

Natalia Silveira, Timothy Dozat, Marie-Catherine de Marneffe, Samuel Bowman, Miriam
Connor, John Bauer and Christopher D. Manning. 2014. A Gold Standard Dependency Corpus
for English. In Proceedings of LREC 2014. (UD English-EWT)

Jeffrey Pennington, Richard Socher and Christopher D. Manning. 2014. GloVe: Global
Vectors for Word Representation. In Proceedings of EMNLP 2014.
