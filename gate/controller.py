"""v0 fixed-threshold controller: (b, d, u) + saturation flag -> action.

Pure function, no state. "Recruit" degrades to plain disclosure in the offline
build (plan §3 E2), so the action set is ANSWER / DELIBERATE / RECOLLECT /
ABSTAIN. Thresholds are exploratory tunables (rationale in notebook entry 4).
"""

from enum import Enum

from opinion import Opinion

U_IGNORANT = 0.85  # above this, confident ignorance: nothing there — ABSTAIN
U_WEAK = 0.35      # weak-resolution band: worth a deeper look if L2 exists


class Action(Enum):
    ANSWER = "answer"
    DELIBERATE = "deliberate"
    RECOLLECT = "recollect"
    ABSTAIN = "abstain"


def route(op: Opinion, saturated: bool, l2_available: bool = True) -> Action:
    """Map an opinion + the substrate's saturation flag to an action.

    - saturated bundle: the geometry cannot be trusted; RECOLLECT from L2
      (or ABSTAIN if there is no L2 to recollect from).
    - u >= U_IGNORANT: confident ignorance — ABSTAIN (say "I don't know").
    - U_WEAK <= u < U_IGNORANT: weak resolution — RECOLLECT if L2 is
      available, else ABSTAIN rather than guess.
    - otherwise resolved: DELIBERATE if ambiguity dominates (d > b, "which
      one do you mean?"), else ANSWER.
    """
    if saturated:
        return Action.RECOLLECT if l2_available else Action.ABSTAIN
    if op.u >= U_IGNORANT:
        return Action.ABSTAIN
    if op.u >= U_WEAK:
        return Action.RECOLLECT if l2_available else Action.ABSTAIN
    if op.d > op.b:
        return Action.DELIBERATE
    return Action.ANSWER


def route_tagged(op, saturated, l2_available=True):
    """E3.2: same policy as route(), but DELIBERATE carries the d-source tag
    ('referential' -> "which one do you mean?"; 'stored' -> "I have two
    different facts about that"). Returns (Action, tag-or-None)."""
    action = route(op, saturated, l2_available)
    if action is Action.DELIBERATE:
        return action, getattr(op, "tag", None)
    return action, None
