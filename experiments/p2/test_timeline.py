"""Leak fix (entry 244 follow-up): CHANGE HISTORY groups same-attr nodes on
the raw attr key, which for rgx facts can be a predicate-key fragment, not
just a canonical slot. When the chain's nodes carry proposition text, the
attr must not be used as a header line."""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import timeline as TL  # noqa: E402


class _FakeGraph:
    def __init__(self, nodes):
        self.nodes = {n["id"]: n for n in nodes}
        self.provisional = {}


class _FakeMem:
    def __init__(self, nodes):
        self.g = _FakeGraph(nodes)


def _node(attr, value, date, text=None, toks=None):
    nid = f"{attr}={value}"
    return {"id": nid, "attr": attr, "value": value,
            "convs": {nid + date: date}, "text": text,
            "toks": toks if toks is not None else set(value.lower().split())}


def test_change_history_uses_text_not_the_predicate_key_attr():
    attr = "enthusiasm_for_integrating_superfood_smoothies_into_routine"
    shared = {"enthusiasm", "superfood", "smoothies", "routine"}
    a = _node(attr, "commendable", "Jan 06, 2026", toks=shared,
             text="Martin Mark's enthusiasm for integrating superfood "
                  "smoothies into his routine is commendable")
    b = _node(attr, "contagious", "May 18, 2029", toks=shared,
             text="Martin Mark's enthusiasm for integrating superfood "
                  "smoothies into his routine is contagious")
    mem = _FakeMem([a, b])
    section = TL.change_history(mem, [a, b])
    assert section  # a 2-value chain was found
    assert attr + ":" not in section
    assert a["text"] in section and b["text"] in section


def test_change_history_falls_back_to_attr_value_when_no_text():
    shared = {"director", "role"}
    a = _node("occupation", "analyst director role", "Jan 06, 2026", toks=shared)
    b = _node("occupation", "senior director role", "May 18, 2029", toks=shared)
    mem = _FakeMem([a, b])
    section = TL.change_history(mem, [a, b])
    assert section
    assert "occupation: analyst director role" in section
    assert "senior director role" in section
