"""p2: fact strength as a continuous latent variable, with tiers as criteria.

Reframing the gate under signal detection theory, which separates two things
the earlier reporting confounded:

  DISCRIMINABILITY (d')  how well the evidence separates supported from
                         unsupported facts. A property of the system.
  CRITERION              where the threshold sits. A deployment choice.

Reporting "precision 0.636" quotes an operating point and hides both. Every
memory product does this. d' is invariant to where you put the cutoff, so it
is the number that says whether the mechanism works at all.

STRUCTURE. Each fact carries a scalar strength assembled from evidence that
costs no model call:

  static   (available at write time)
    grounding      are the subject and object actually present in the span?
    modality       is it asserted as ACTUAL, or hedged/future/negated/...?
    form           is it a well-formed proposition?

  dynamic  (accrues with exposure -- the survival/pruning term)
    activations    later sessions that revisit the fact's subject AND object
                   without contradicting it
    contradictions later sessions asserting a different object for the same
                   (subject, relation)
    dormancy       sessions elapsed with no activation

The dynamic terms are the pruning half of the lifecycle. Overproduction
followed by activity-dependent elimination is the normal shape; extraction
already does the overproducing (~90% junk on real turns, entry 27) and no
memory system in the field implements the elimination. A peripheral one-off
("the eBird app tracks bird sightings") never recurs; a central fact about the
user's employer or city recurs constantly. That asymmetry is the signal.

TESTABLE PREDICTION, which is the point of building it this way: if the
dynamic terms carry information, d' should RISE with the number of sessions
observed. "Gets better with use" stated as something falsifiable rather than
as marketing. If d' is flat in exposure, the survival mechanism is dead weight
and we will know.

Weights are NOT fitted here. They are set to plainly-stated defaults so the
first d' is honest; fitting them on dev comes after we know there is a signal
to fit.
"""

import math
import re
from collections import defaultdict

from gate import wellformed, grounded, modality
from ingest import fact_key

# evidence weights -- deliberate, unfitted defaults
# Static-evidence weights. The RELATIVE values are from a balanced logistic fit
# on the 130-item dev support labels (entry 37): grounded > actual > form,
# rescaled so form=1.0. Fitting barely moved held-out d' (2.07 hand-set ->
# 2.16 fitted), confirming the hand-set were already near-optimal and that the
# discriminability ceiling is the (three binary) FEATURES, not the weights.
W_FORM = 1.0
W_GROUND = 2.2      # dominant support signal (fit: +2.75 vs form +1.27)
W_ACTUAL = 1.5      # fit: +1.96 vs form +1.27
W_ACTIVATION = 1.0
W_CONTRADICTION = 2.0
W_DORMANCY = 0.15


def _content(x):
    stop = {"the", "a", "an", "of", "in", "at", "to", "for", "and", "or", "my",
            "your", "his", "her", "their", "our", "its", "this", "that", "is",
            "was", "are", "were", "be", "been", "new", "some", "any", "one"}
    return {t for t in re.findall(r"\w+", str(x).lower())
            if len(t) > 2 and t not in stop}


def static_evidence(span, triple):
    """Write-time evidence. No history required."""
    form_ok, _ = wellformed(triple)
    ground_ok, _ = grounded(span, triple) if form_ok else (False, "")
    mod = modality(span, triple)[0] if form_ok else None
    return {"form": 1.0 if form_ok else 0.0,
            "grounded": 1.0 if ground_ok else 0.0,
            "actual": 1.0 if mod == "ACTUAL" else 0.0,
            "modality": mod}


def strength(ev, activations=0, contradictions=0, dormancy=0):
    """Scalar memory strength. Monotone in evidence, penalised by challenge
    and by dormancy. Log terms so a fact revisited twenty times does not
    dominate one revisited three times."""
    return (W_FORM * ev["form"]
            + W_GROUND * ev["grounded"]
            + W_ACTUAL * ev["actual"]
            + W_ACTIVATION * math.log1p(activations)
            - W_CONTRADICTION * math.log1p(contradictions)
            - W_DORMANCY * dormancy)


# --------------------------------------------------------------- survival

class SurvivalIndex:
    """Tracks activation, contradiction and dormancy per fact across sessions.

    ACTIVATION requires the later span to revisit the fact's OBJECT as well as
    its subject. Subject alone is useless here: most facts have the speaker as
    subject, so every user turn would activate every speaker fact and the
    signal would be constant. The object is what makes a fact specific, so it
    is what a genuine revisit must touch.
    """

    def __init__(self):
        self.facts = {}          # key -> dict
        self.sessions_seen = set()

    def observe_fact(self, key, triple, span, session_id, ev):
        f = self.facts.get(key)
        if f is None:
            f = {"triple": triple, "first_session": session_id, "ev": ev,
                 "activations": set(), "contradictions": set(),
                 "last_session": session_id}
            self.facts[key] = f
        else:
            f["last_session"] = session_id
        self.sessions_seen.add(session_id)

    def observe_span(self, text, session_id, triples_in_span):
        """A later span tests every fact it touches."""
        self.sessions_seen.add(session_id)
        toks = _content(text)
        # contradiction: this span asserts a different object under the same key prefix
        asserted = defaultdict(set)
        for tr in triples_in_span:
            k = fact_key(tr)
            asserted[(k[0], k[1])].add(k[2])

        for key, f in self.facts.items():
            if f["first_session"] == session_id:
                continue                       # a fact cannot test itself
            subj, rel, obj = key
            obj_toks = _content(obj)
            if not obj_toks or not (obj_toks & toks):
                continue                       # span does not revisit this fact
            others = asserted.get((subj, rel), set())
            if others and obj not in others:
                f["contradictions"].add(session_id)
            else:
                f["activations"].add(session_id)

    def score(self, key, current_session=None):
        f = self.facts[key]
        acts = len(f["activations"])
        cons = len(f["contradictions"])
        last_active = max(f["activations"] | {f["first_session"]})
        dormancy = 0
        if current_session is not None:
            try:
                dormancy = max(0, int(current_session) - int(last_active))
            except (TypeError, ValueError):
                dormancy = 0
        return {"strength": strength(f["ev"], acts, cons, dormancy),
                "activations": acts, "contradictions": cons,
                "dormancy": dormancy, "triple": f["triple"],
                "modality": f["ev"]["modality"]}
