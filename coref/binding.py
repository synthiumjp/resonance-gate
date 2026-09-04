"""Chomsky Binding Theory (Government & Binding, 1981) as dependency-tree
vetoes for candidate pronoun-coreference links. Verified against
https://en.wikipedia.org/wiki/Binding_(linguistics):

  Condition A: an anaphor (reflexive/reciprocal) MUST be bound locally
    (have its antecedent within the same clause).
  Condition B: a pronoun must NOT be bound by a c-commanding argument
    within its local clause.

Condition C (an R-expression can't be bound by a c-commanding pronoun --
the cataphora case, "She said Rachel left") is deliberately out of scope:
it needs c-command reasoning that crosses clause boundaries, which the
coarse, same-clause-only c-command approximation below does not attempt.
Cataphora is rare and marked in natural chat text, so skipping it is a
cheap simplification, not a precision risk on what this module DOES decide.

Scope, stated plainly: this module only ever fires WITHIN a single clause.
It has no opinion on cross-sentence/cross-turn coreference -- the majority
case in chat transcripts (see centering.py for that). Its only job is to
VETO structurally-impossible same-clause links before they reach a
statistical model's proposal; it never proposes a link itself. A false
veto only costs recall (an already-rare same-clause case gets skipped);
it can never manufacture a false merge.

Tokens are duck-typed to the subset of the spaCy Token API this needs:
`.text`, `.pos_`, `.dep_`, `.head`. Real spaCy tokens satisfy this
directly -- no adapter required.
"""

from typing import Protocol


class Token(Protocol):
    text: str
    pos_: str
    dep_: str
    head: "Token"


REFLEXIVES = {
    "himself", "herself", "itself", "myself", "yourself",
    "ourselves", "yourselves", "themselves",
}
RECIPROCALS = {"each other", "one another"}

# spaCy dep labels marking a clause boundary: crossing one of these on the
# way up leaves the binding domain of the token below it.
_CLAUSE_BOUNDARY_DEPS = {"relcl", "advcl", "ccomp", "acl", "xcomp"}


def is_reflexive(token: Token) -> bool:
    t = token.text.lower()
    return t in REFLEXIVES or t in RECIPROCALS


def clause_root(token: Token) -> Token:
    """Walk up the dependency tree to the root of TOKEN's local clause:
    the sentence ROOT, or the first clause-introducing token encountered
    on the path up (inclusive)."""
    t = token
    seen = {id(t)}
    while t.dep_ != "ROOT" and t.head is not t:
        if t.dep_ in _CLAUSE_BOUNDARY_DEPS:
            break
        t = t.head
        if id(t) in seen:      # malformed/cyclic parse -- bail safely
            break
        seen.add(id(t))
    return t


def same_clause(a: Token, b: Token) -> bool:
    return clause_root(a) is clause_root(b)


def c_commands(a: Token, b: Token) -> bool:
    """Coarse c-command check, sufficient for the subject/object-of-the-
    same-verb case that dominates Condition B violations in practice:
    A c-commands B if they are siblings (share a head) or A is on B's
    head-chain within the same clause as A."""
    if a is b:
        return False
    if a.head is b.head:
        return True
    t = b
    while t.dep_ != "ROOT" and t.head is not t and same_clause(t, a):
        t = t.head
        if t is a:
            return True
    return False


def violates_binding(pronoun: Token, candidate: Token) -> bool:
    """True => VETO this candidate link outright. False => binding theory
    has no opinion (NOT an endorsement -- just not excluded)."""
    if is_reflexive(pronoun):
        # Condition A: reflexive MUST bind locally.
        return not same_clause(pronoun, candidate)
    if pronoun.pos_ == "PRON":
        # Condition B: plain pronoun must NOT bind to a same-clause
        # c-commanding argument.
        if same_clause(pronoun, candidate) and c_commands(candidate, pronoun):
            return True
    return False
