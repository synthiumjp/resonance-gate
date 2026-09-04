"""Unit tests for the conservative entity-linking gate wrapping
Registry.resolve() (encoder/registry.py) via a duck-typed fake."""

from entity_link import Link, link_entity


class _Empty:
    def __len__(self):
        return 0

    def resolve(self, term, top=2):
        return []


class _FakeRegistry:
    """hits_by_term: {mention: [(name, cosine), ...]} best-first, as
    Registry.resolve() returns."""

    def __init__(self, hits_by_term):
        self._hits = hits_by_term

    def __len__(self):
        return 1   # non-empty for these tests

    def resolve(self, term, top=2):
        return self._hits.get(term, [])[:top]


def test_empty_registry_is_new():
    decision, name, margin = link_entity(_Empty(), "Rachel")
    assert decision is Link.NEW
    assert name is None


def test_high_cosine_clear_margin_confident():
    reg = _FakeRegistry({"Rachel": [("Rachel", 0.95), ("Rachael", 0.40)]})
    decision, name, margin = link_entity(reg, "Rachel")
    assert decision is Link.CONFIDENT
    assert name == "Rachel"


def test_low_cosine_registers_new():
    reg = _FakeRegistry({"Zephyr": [("Rachel", 0.30), ("Tom", 0.25)]})
    decision, name, margin = link_entity(reg, "Zephyr")
    assert decision is Link.NEW


def test_close_tie_is_possible_not_confident():
    """'Tom' vs. two candidates close together ('Tom Fischer' the
    coworker, 'Tom Reyes' the cousin) -- must NOT auto-merge on a
    near-tie, per the false-merge > missed-link cost asymmetry."""
    reg = _FakeRegistry({"Tom": [("Tom Fischer", 0.82), ("Tom Reyes", 0.79)]})
    decision, name, margin = link_entity(reg, "Tom")
    assert decision is Link.POSSIBLE
    assert name == "Tom Fischer"
