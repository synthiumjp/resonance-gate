"""Entry 249: labeled hearsay in the judged QA context.

Two things must hold, and the second is the one that protects the banked
numbers:

  1. RG_HEARSAY=1 appends hearsay lines AFTER every corroborated candidate,
     each carrying the HEARSAY label, plus exactly one composer rule.
  2. With RG_HEARSAY unset the context and the rule block are BYTE-IDENTICAL
     to what the entry-110 config produced -- otherwise the LLM arm is not a
     fixed baseline any more and `--reuse` economics are void.

Runs without models or a judge: the retrieval and the composer call are both
stubbed, because what is under test is the context ASSEMBLY, not retrieval.

    python3 -m pytest experiments/p2/test_hearsay_qa.py
"""
import importlib
import os
import sys
import types

import pytest

_P2 = os.path.dirname(os.path.abspath(__file__))
_OFFICIAL = os.path.join(_P2, "halumem_official")


def _load(hearsay_on):
    """Import eval_rgp2 fresh under a given RG_HEARSAY, with its heavy
    dependencies stubbed. The module reads the flag at import time."""
    for p in (_P2, _OFFICIAL):
        if p not in sys.path:
            sys.path.insert(0, p)

    # harness-local modules that live in the HaluMem eval dir, not our tree
    for name, attrs in (("llms", {"llm_request": lambda p: "stub-answer"}),
                        ("prompts", {"PROMPT_MEMZERO":
                                     "CONTEXT:\n{context}\nQ: {question}"})):
        mod = types.ModuleType(name)
        for k, v in attrs.items():
            setattr(mod, k, v)
        sys.modules[name] = mod

    os.environ["RG_RETRIEVE_V3"] = "1"
    os.environ["RG_EXTRACT_V5"] = "1"
    if hearsay_on:
        os.environ["RG_HEARSAY"] = "1"
    else:
        os.environ.pop("RG_HEARSAY", None)

    sys.modules.pop("eval_rgp2", None)
    return importlib.import_module("eval_rgp2")


class _FakeIndex:
    owner = "Martin Mark"

    def __init__(self, hearsay):
        self.hearsay = hearsay


def _stub_retrieval(mod, facts, hearsay_facts):
    """Stub both retrieval layers so only assembly is exercised."""
    mod.RV3.retrieve_facts_v3 = (
        lambda index, question, **kw:
        hearsay_facts if index is not None and getattr(
            index, "_is_hearsay", False) else facts)
    mod.RV.format_fact = lambda d, owner=None: d["line"]


FACTS = [{"line": "[confirmed x3, 2025-09-04] Martin Mark's job is engineer."}]
HEARSAY = [{"line": "[unconfirmed(once), 2025-09-06] Martin Mark enjoys jazz."}]


def test_hearsay_off_is_byte_identical():
    mod = _load(hearsay_on=False)
    hs_index = _FakeIndex(hearsay=object())
    hs_index._is_hearsay = False
    _stub_retrieval(mod, FACTS, HEARSAY)

    _, context = mod.compose_answer(mem=None, question="What is his job?",
                                    index=hs_index)

    assert context == FACTS[0]["line"]
    assert "HEARSAY" not in context
    # the entry-110 rule block must be untouched
    assert not mod.CAL.rstrip().endswith("4.")
    assert "HEARSAY" not in mod.CAL


def test_hearsay_on_appends_labeled_lines_last():
    mod = _load(hearsay_on=True)
    hearsay_index = _FakeIndex(hearsay=None)
    hearsay_index._is_hearsay = True
    index = _FakeIndex(hearsay=hearsay_index)
    _stub_retrieval(mod, FACTS, HEARSAY)

    _, context = mod.compose_answer(mem=None, question="Does he like jazz?",
                                    index=index)

    lines = context.split("\n")
    assert lines[0] == FACTS[0]["line"], "corroborated fact must come first"
    assert lines[-1].startswith(mod.HEARSAY_LABEL), \
        "hearsay must be appended last, labeled"
    assert HEARSAY[0]["line"] in lines[-1]
    # the label must not leak into the corroborated line
    assert mod.HEARSAY_LABEL not in lines[0]


def test_hearsay_rule_added_only_when_lines_present():
    mod = _load(hearsay_on=True)
    hearsay_index = _FakeIndex(hearsay=None)
    hearsay_index._is_hearsay = True
    index = _FakeIndex(hearsay=hearsay_index)

    captured = {}
    sys.modules["llms"].llm_request = lambda p: captured.setdefault("p", p)
    mod.llm_request = lambda p: captured.setdefault("p", p) or "stub"

    # no hearsay retrieved -> no rule
    _stub_retrieval(mod, FACTS, [])
    mod.compose_answer(mem=None, question="q", index=index)
    assert "HEARSAY" not in captured["p"]

    # hearsay retrieved -> exactly one rule, appended once
    captured.clear()
    _stub_retrieval(mod, FACTS, HEARSAY)
    mod.compose_answer(mem=None, question="q", index=index)
    assert captured["p"].count(mod.HEARSAY_RULE) == 1


def _fake_mem():
    node = lambda a, v: {"attr": a, "value": v, "n_mentions": 2,
                         "convs": {"c1": "2025-09-04"}, "text": f"{a} is {v}"}
    return types.SimpleNamespace(g=types.SimpleNamespace(
        nodes={"n1": node("job", "engineer")},
        provisional={},
        hearsay={"h1": node("music_preference", "jazz")}))


def _stub_models(monkeypatch, RV3):
    """Encoder stub -- the index's BM25/flag logic is what is under test, and
    loading bge-small + a cross-encoder to check a branch is not worth it."""
    import numpy as np
    bi = types.SimpleNamespace(
        encode=lambda texts, **kw: np.zeros((len(texts), 4), dtype="float32"))
    monkeypatch.setattr(RV3, "_models", lambda: (bi, object()))


@pytest.mark.parametrize("flag_on", [False, True])
def test_index_hearsay_subindex_follows_flag(monkeypatch, flag_on):
    """The index must gain a hearsay sub-index ONLY under the flag. With it
    off there is no second index, so nothing competes for top_n and the
    banked retrieval behaviour is preserved exactly."""
    _load(hearsay_on=flag_on)
    import retrieve_v3 as RV3
    _stub_models(monkeypatch, RV3)

    index = RV3.IndexV3(_fake_mem())

    # the main index never contains hearsay, in either state
    assert [d["attr"] for d in index.facts] == ["job"]
    if flag_on:
        assert index.hearsay is not None
        assert [d["attr"] for d in index.hearsay.facts] == ["music_preference"]
        # and the sub-index must not recurse
        assert index.hearsay.hearsay is None
    else:
        assert index.hearsay is None
