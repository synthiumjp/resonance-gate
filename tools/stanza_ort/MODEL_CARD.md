---
license: apache-2.0
language:
- en
library_name: onnxruntime
tags:
- stanza
- dependency-parsing
- part-of-speech
- lemmatization
- onnx
---

# sourcedrecall English parser models (Stanza 1.14.0, ONNX)

These are the English models of [Stanza](https://github.com/stanfordnlp/stanza) 1.14.0
(tokenizer, multi-word token expander, part-of-speech tagger, lemmatizer and dependency
parser, with their character language models and word vectors), converted so they run on
[ONNX Runtime](https://onnxruntime.ai) and numpy without PyTorch.

They are used by [sourcedrecall](https://github.com/synthiumjp/sourcedrecall), a local
memory for AI assistants whose parser reads the user's messages with Stanza's dependency
parses. Running them without PyTorch cuts its install by about 600 MB.

## Same parses as Stanza

The runtime that loads these files (`stanza_ort`, in the sourcedrecall repository) was
checked against Stanza 1.14.0 on PyTorch on 7,755 texts (246,560 words): every LoCoMo
conversation turn, the sourcedrecall benchmark cases, its parser test sentences, and long
and unusual inputs (lists, code mixed with prose, emoji, 8,000-character messages). Every
field of every word (text, upos, xpos, feats, lemma, head, deprel, character offsets) and
every sentence split was identical, one text at a time and in batches. The networks run
in fp32; outputs differ from PyTorch's by about 1e-5 in the raw scores, which changed no
decision in that set. Checked on macOS arm64.

## Files

`sourcedrecall-parser-en-stanza1.14.0.tar.gz` unpacks to:

| file | what it is |
|---|---|
| `tok.onnx` | tokenizer and sentence splitter network |
| `pos.onnx` | part-of-speech and morphological features tagger |
| `dep.onnx` | dependency parser (arc and label scorers) |
| `charlm_fwd.onnx`, `charlm_bwd.onnx` (+ `.npz`) | character language models, shared by the tagger and the parser |
| `pretrain_emb.npy` | the word vectors the tagger and parser use |
| `lemma.npz`, `mwt.npz` | weights of the lemmatizer and multi-word token sequence models |
| `config.json` | vocabularies, model settings and the lemma dictionaries |

sha256 of the archive: `921281ed755e8a4454cce27df56e18557123920e1df4b02443cade72e0e2f105`

## How they were made

`tools/stanza_ort/convert.py` in the sourcedrecall repository loads Stanza 1.14.0's English
models and exports each network with `torch.onnx.export`; two layers were rewritten in
exactly equivalent form for export (`nn.Bilinear` as an einsum, a boolean identity mask
from `arange`). `tools/stanza_ort/parity.py` is the comparison above.

## Licence and credit

The models are Stanza's, by the Stanford NLP Group, released under the Apache License 2.0;
this conversion is released under the same licence. See `NOTICE`.

Peng Qi, Yuhao Zhang, Yuhui Zhang, Jason Bolton and Christopher D. Manning. 2020.
Stanza: A Python Natural Language Processing Toolkit for Many Human Languages.
In Proceedings of ACL 2020: System Demonstrations.
