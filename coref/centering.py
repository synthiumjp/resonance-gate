"""Grosz, Joshi & Weinstein 1995 Centering Theory as a per-session
discourse-salience tracker for cross-turn pronoun resolution. Primary
source verified via PDF fetch: https://aclanthology.org/J95-2003/

This is the module that does the cross-sentence work binding.py cannot:
it tracks which entity is the current discourse topic (Cb, the
backward-looking center) turn over turn, and ranks each turn's entities
by salience (Cf, the forward-looking centers list -- grammatical role
first, then linear order) so a pronoun in turn N can be preferentially
resolved to whichever candidate is currently most salient, rather than to
whatever a similarity-only model happens to score highest.

Cb(Un) = the highest-ranked element of Cf(Un-1) that is realized in Un
(i.e. also mentioned this turn); undefined (None) if none is. Transition
per utterance:
  CONTINUE -- Cb unchanged AND it is the top-ranked Cf entity this turn.
  RETAIN   -- Cb unchanged but no longer top-ranked (topic persists, but
              expressed less centrally -- discourse theory's early-warning
              signal that things are getting less coherent).
  SHIFT    -- Cb changed.
"""

from dataclasses import dataclass, field
from enum import Enum


class Transition(Enum):
    CONTINUE = "continue"
    RETAIN = "retain"
    SHIFT = "shift"


ROLE_RANK = {
    "nsubj": 0, "nsubjpass": 0, "csubj": 0,
    "dobj": 1, "obj": 1, "attr": 1,
    "iobj": 2, "pobj": 2, "obl": 2,
}
_OTHER_RANK = 9


def _role_rank(dep_label):
    return ROLE_RANK.get(dep_label, _OTHER_RANK)


@dataclass
class CenteringState:
    """One instance per conversation session (not per turn)."""
    cb: str | None = None
    cf_history: list = field(default_factory=list)   # ranked name lists, one per turn

    def update(self, turn_entities):
        """turn_entities: [(canonical_name, dep_label), ...] realized this
        turn, AFTER coreference resolution (so a resolved pronoun carries
        its antecedent's canonical name, not its surface text). Returns
        the Transition for this turn, or None for the session's first turn
        (Cb is undefined before any prior utterance exists)."""
        cf = [name for name, _ in
              sorted(turn_entities, key=lambda e: _role_rank(e[1]))]
        is_first_turn = not self.cf_history
        prev_cf = self.cf_history[-1] if self.cf_history else []
        realized = {name for name, _ in turn_entities}

        new_cb = next((n for n in prev_cf if n in realized), None)
        if new_cb is None:
            new_cb = cf[0] if cf else self.cb

        if is_first_turn:
            transition = None
        elif new_cb == self.cb and cf and cf[0] == new_cb:
            transition = Transition.CONTINUE
        elif new_cb == self.cb:
            transition = Transition.RETAIN
        else:
            transition = Transition.SHIFT

        self.cb = new_cb
        self.cf_history.append(cf)
        return transition

    def rank_of(self, name):
        """0 = most salient in the most recently completed turn; larger is
        less salient; len(cf)+1 if NAME wasn't mentioned last turn at all."""
        cf = self.cf_history[-1] if self.cf_history else []
        return cf.index(name) if name in cf else len(cf) + 1
