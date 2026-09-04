"""Combines the binding-theory hard filter (binding.py) with the
centering-theory salience ranking (centering.py) to gate statistically
proposed pronoun links (e.g. from fastcoref). Mirrors Lee et al. 2013's
precision-ranked sieve philosophy (https://aclanthology.org/J13-4004/):
cheap, near-certain rules run first and can only ever REJECT a proposal;
the salience check only ever demotes an accepted proposal to a
lower-confidence bucket. The statistical model's score can never override
a binding-theory veto.

Decisions, in order of confidence:
  CONFIDENT -- write the resolved fact normally.
  POSSIBLE  -- write it, but keep it out of contradiction detection until
               corroborated (a false merge costs more than a missed fact
               -- see the conversation's precision/recall tradeoff notes).
  REJECTED  -- drop the candidate link; the fact is simply not extracted
               this pass (a miss, not a wrong answer).
"""

from enum import Enum

from binding import violates_binding
from centering import CenteringState


class Decision(Enum):
    CONFIDENT = "confident"
    POSSIBLE = "possible"
    REJECTED = "rejected"


DEFAULT_MAX_SALIENCE_RANK = 1     # accept top-2 most-salient candidates outright
DEFAULT_MIN_MODEL_SCORE = 0.5


def gate_pronoun_link(pronoun_token, candidate_token, candidate_name,
                       model_score, centering: CenteringState,
                       max_salience_rank=DEFAULT_MAX_SALIENCE_RANK,
                       min_model_score=DEFAULT_MIN_MODEL_SCORE):
    """Returns (Decision, reason_str)."""
    if violates_binding(pronoun_token, candidate_token):
        return Decision.REJECTED, "binding-theory-veto"

    if model_score < min_model_score:
        return Decision.REJECTED, "low-model-confidence"

    rank = centering.rank_of(candidate_name)
    if rank <= max_salience_rank:
        return Decision.CONFIDENT, f"salience-rank-{rank}"

    return Decision.POSSIBLE, f"salience-rank-{rank}-below-threshold"
