"""Leak fix (entry 244 follow-up): the QA context renderer, format_fact(),
never got the entry-244 "use the node's own proposition text" treatment that
every other renderer (memory_api.context_block, eval_rgp2._fact_str,
eval_rgp2.search_memories._v) received, so the judged QA context leaked raw
predicate-key attrs from the rgx extractor ("change_highlight: martin
mark's willingness...", "openness_to_exploring_new_experiences_...: ...").
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import retrieve as RV  # noqa: E402


def _node(attr, value, text=None, n=2):
    return {"attr": attr, "value": value, "text": text, "n_mentions": n,
            "convs": {"c0": "2026-01-01"}}


def test_format_fact_uses_text_when_present():
    """The leak: an rgx node's predicate-key attr must never surface when
    the node carries its own full proposition."""
    nd = _node("openness_to_exploring_new_experiences_such_as_action_games",
              "a testament to martin mark's commitment to innovation",
              text="Martin Mark's openness to exploring new experiences "
                   "such as action games demonstrates his commitment to "
                   "innovation")
    line = RV.format_fact(nd)
    assert nd["text"] in line
    assert "openness_to_exploring_new_experiences_such_as_action_games:" not in line


def test_format_fact_falls_back_to_atom_when_no_text():
    """LLM-cache facts have no "text" -- today's format stays unchanged."""
    nd = _node("employer", "acme", text=None)
    line = RV.format_fact(nd)
    assert "employer: acme" in line


def test_format_fact_text_used_regardless_of_rg_qa_props_env():
    """Text must not be gated behind RG_QA_PROPS -- that flag only controls
    the fallback path (propositions.render) for facts that have no text."""
    nd = _node("change_highlight", "martin mark's willingness to try",
              text="Martin Mark's willingness to try unconventional pet "
                   "choices changed")
    prev = os.environ.pop("RG_QA_PROPS", None)
    try:
        line = RV.format_fact(nd)
    finally:
        if prev is not None:
            os.environ["RG_QA_PROPS"] = prev
    assert nd["text"] in line
    assert "change_highlight:" not in line
