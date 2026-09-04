"""The refusal suite as a gate (e270).

rgx/refusal_cases.py is the inventory (CommitmentBank's four
entailment-cancelling operators) and tools/refusal_report.py prints the
matrix. This runs the same cases as tests so a regression is red rather than
merely visible.

DIR is not decoration. An MFT that passes because the parser emitted nothing
proves nothing -- it is equally consistent with the parser simply failing on
the sentence. The matched declarative control is what shows the OPERATOR did
the work.
"""
import pytest

from rgx import Extractor
from rgx.refusal_cases import CASES, INVARIANCE

OWNER = "Alex Reyes"


@pytest.fixture(scope="module")
def ex():
    return Extractor(owner_name=OWNER)


def _texts(ex, s, role):
    ex.reset_world()
    return [r.text for r in ex.extract_turn(s, role=role)]


def _id(c):
    return f"{c['capability']}::{c['operator']}"


@pytest.mark.parametrize("c", [c for c in CASES if c.get("must_not")],
                         ids=_id)
def test_mft_the_operator_blocks_the_assertion(ex, c):
    out = _texts(ex, c["irrealis"], c["role"])
    bad = [o for o in out if c["must_not"].lower() in o.lower()]
    if c.get("unless_contains"):
        bad = [o for o in bad
               if c["unless_contains"].lower() not in o.lower()]
    assert not bad, f"{c['irrealis']!r} asserted {c['must_not']!r}: {bad}"


@pytest.mark.parametrize("c", [c for c in CASES if c.get("control_asserts")],
                         ids=_id)
def test_dir_the_matched_declarative_still_asserts(ex, c):
    """Without this, a refusal test cannot tell suppression from failure."""
    out = _texts(ex, c["control"], c.get("control_role", "user"))
    assert any(c["control_asserts"].lower() in o.lower() for o in out), (
        f"control {c['control']!r} did not assert "
        f"{c['control_asserts']!r}: {out}")


@pytest.mark.parametrize("c", [c for c in CASES if c.get("assert_instead")],
                         ids=_id)
def test_the_frame_still_owes_its_own_fact(ex, c):
    """A negation asserts its negative; a FACTIVE predicate presupposes its
    complement. Refusing everything is not correctness."""
    out = _texts(ex, c["irrealis"], c["role"])
    assert any(c["assert_instead"].lower() in o.lower() for o in out), (
        f"{c['irrealis']!r} should still assert "
        f"{c['assert_instead']!r}: {out}")


@pytest.mark.parametrize(
    "cap,needle,role,unless,variant",
    [(s["capability"], s["needle"], s["role"],
      tuple(u.lower() for u in s.get("unless", ())), v)
     for s in INVARIANCE for v in s["variants"]],
    ids=lambda x: x if isinstance(x, str) else None)
def test_inv_refusal_survives_rewording_the_marker(ex, cap, needle, role,
                                                    unless, variant):
    """The invariance row is what caught e270: "if" was suppressed and three
    paraphrases of the same operator were not, because they carry no `mark`
    at all -- Stanza reads them as VERBS heading the clause."""
    out = _texts(ex, variant, role)
    bad = [o for o in out if needle.lower() in o.lower()]
    if unless:
        bad = [o for o in bad if not any(u in o.lower() for u in unless)]
    assert not bad, f"{variant!r} asserted {needle!r} unmarked: {bad}"
