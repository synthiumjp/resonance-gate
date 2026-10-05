"""stanza_ort, the PyTorch-free runtime, must parse exactly as Stanza does
(2026-10-05). Runs when both are installed and RGX_PARSER_MODELS names the
converted models; the full parity check is tools/stanza_ort/parity.py."""
import os

import pytest

stanza = pytest.importorskip("stanza")
stanza_ort = pytest.importorskip("stanza_ort")
MODELS = os.environ.get("RGX_PARSER_MODELS")
pytestmark = pytest.mark.skipif(
    not MODELS or not os.path.exists(os.path.join(MODELS or "", "config.json")),
    reason="RGX_PARSER_MODELS not set to converted models")

TEXTS = [
    "I moved to Lisbon in 2019 and my sister still lives in Leeds.",
    "Got promoted to lead last week!! Can't believe it.",
    "Please never add comments to my code.",
    "Here's the error:\n\nModuleNotFoundError: no module named 'x'\n\nI already tried reinstalling.",
    "I'm a nurse at St Vincent's; my dog Biscuit is a beagle 🐶.",
]


def _sig(doc):
    return [[(w.id, w.text, w.upos, w.xpos, w.feats, w.lemma, w.head, w.deprel)
             for w in s.words] for s in doc.sentences]


def test_the_same_parse_one_at_a_time_and_in_bulk():
    ref = stanza.Pipeline("en", processors="tokenize,pos,lemma,depparse",
                          use_gpu=False, verbose=False, download_method=None)
    ort = stanza_ort.Pipeline(MODELS)
    for t in TEXTS:
        assert _sig(ort(t)) == _sig(ref(t)), t
    bulk = ort.bulk_process([stanza_ort.Document([], text=t) for t in TEXTS])
    assert [_sig(d) for d in bulk] == [_sig(ref(t)) for t in TEXTS]


def test_rgx_uses_stanza_ort_when_its_models_are_installed(monkeypatch):
    import rgx
    monkeypatch.setenv("RGX_PARSER_MODELS", MODELS)
    monkeypatch.delenv("RGX_PARSER", raising=False)
    ex = rgx.Extractor(owner_name="Dana Cole")
    assert ex._parser().Document is stanza_ort.Document
    monkeypatch.setenv("RGX_PARSER", "stanza")
    assert rgx.ort_models_dir() is None
