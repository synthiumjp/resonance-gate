"""p2 two-path architecture: separate the assertion gate from the comparison gate.

Entry 40 measured the differentiator's blocker: the write gate reached 0.905
support precision partly by dropping every fact with a natural descriptive
relation ("set a personal best time in", "pre-approved for") via its length cap
and known-predicate whitelist -- which is exactly the update facts contradiction
detection needs. Relaxing the gate globally halves support precision for zero
support-recall gain (entry 40). Support and contradiction have CONFLICTING needs
on the relation-form knob, so they get TWO gates over the SAME extractions:

  ASSERTION path  (gate.assess, unchanged): high precision. What the system
                  will STATE as fact. Descriptive-relation facts excluded --
                  correct there.
  COMPARISON path (this module): higher recall. Keeps descriptive-relation
                  facts as contradiction CANDIDATES. A candidate may NOT be
                  asserted standalone; its only job is to enter contradiction
                  detection, where precision is supplied downstream by the RCI
                  commensurability gate + provenance, NOT by the write gate.

The design claim being tested: a fact can be a valid contradiction signal
without being clean enough to assert. "I | set a personal best time in | 27:12"
is not something the system should volunteer as a standalone fact (descriptive
relation, low assertion precision), but when a later "25:50" appears under the
same key it IS a legitimate change to surface WITH BOTH RECEIPTS. Disagreement-
with-receipts is self-verifying in a way a bare assertion is not.

No model call. Reuses gate stages (wellformed structural checks, grounding,
subject-contiguity, modality) MINUS the relation-vocabulary whitelist, plus the
scope filter and the RCI change classifier.
"""

import os
import re
import sys
from collections import defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from gate import (grounded, subject_contiguous, modality, _CLAUSE_SUBJ,
                  _BAD_REL, _REL_PREFIX)
from schema import Scope
from rci import classify_pair, UPDATE, NOISE, MULTI_VALUE, CATEGORICAL

# comparison-path relation length cap: looser than the assertion gate's 4, but
# still bounded so a whole clause in the relation slot is rejected.
_COMPARISON_REL_MAX = 7


def comparison_wellformed(triple):
    """Relaxed well-formedness for the COMPARISON path. Keeps the structural
    checks that guard against garbage (null fields, clause-subjects, relation
    that is a stopword) but DROPS the known-predicate whitelist -- so
    'set a personal best time in' survives here while it dies in the assertion
    gate. This is the one deliberate relaxation, and it is confined to the
    comparison path so assertion precision is untouched."""
    s, r, o = [str(x).strip() for x in triple]
    if not s or not r or not o:
        return False, "empty field"
    if o.lower() in ("none", "") or s.lower() in ("none", "", "utterance"):
        return False, "null field"
    if r.lower() in _BAD_REL:
        return False, "relation is a stopword"
    if len(_REL_PREFIX.sub("", r).split()) > _COMPARISON_REL_MAX:
        return False, "relation is a clause"
    if len(s.split()) > 6:
        return False, "subject is a clause"
    if _CLAUSE_SUBJ.search(s):
        return False, "subject is not an entity"
    return True, "ok"


def comparison_candidate(span, triple):
    """Is this triple a valid CONTRADICTION CANDIDATE? Structural + grounded +
    in-scope-able + ACTUAL, but NOT required to have a whitelisted relation.
    Scope is checked by the caller (needs the session Scope object)."""
    ok, why = comparison_wellformed(triple)
    if not ok:
        return None, why
    if not grounded(span, triple)[0]:
        return None, "ungrounded"
    if not subject_contiguous(span, triple)[0]:
        return None, "fabricated subject"
    mod = modality(span, triple)[0]
    if mod != "ACTUAL":
        return None, f"modality={mod}"
    return {"triple": tuple(triple), "modality": mod}, "candidate"


# ------------------------------------------------- relation normalisation

_REL_STOP = {"a", "an", "the", "my", "to", "in", "at", "for", "of", "on",
             "so", "far", "currently", "recently", "just", "now", "been",
             "have", "has", "had", "am", "is", "are", "was", "were"}


def norm_relation(r):
    """Canonical relation key for matching two mentions of the same attribute.
    Light: lowercase, drop auxiliaries/determiners/adverbs, keep the content
    verb + any noun, so 'have tried' / 'tried' align and 'set a personal best
    time in' / 'set personal best' align. NOT semantic -- a heavier synonym
    step (works-at/employed-by) is deferred; this only collapses surface
    variation of the same phrasing."""
    words = [w for w in re.findall(r"[a-z]+", r.lower()) if w not in _REL_STOP]
    return " ".join(words[:3])


def norm_subject(s):
    s = re.sub(r"\s*\([^)]*\)\s*$", "", str(s).strip().lower())
    s = re.sub(r"^(the|a|an|my|our)\s+", "", s)
    if re.match(r"^i(\s|'|$)", s) or s in ("me", "myself"):
        return "@speaker"
    return re.sub(r"\s+", " ", s).strip(" .,!?")


# ------------------------------------------------- contradiction detection

def detect_contradictions(candidates):
    """candidates: list of dicts {triple, span_id, session}. Groups by
    (norm_subject, norm_relation), and for each key with >1 distinct object
    runs the RCI classifier. Returns the reliable-change alerts and the full
    classification, each carrying both receipts."""
    by_key = defaultdict(list)
    for c in candidates:
        t = c["triple"]
        by_key[(norm_subject(t[0]), norm_relation(t[1]))].append(c)

    alerts, multivalue, noise = [], [], []
    for key, items in by_key.items():
        objs = {}
        for it in items:
            objs.setdefault(it["triple"][2], it)
        if len(objs) < 2:
            continue
        ovals = list(objs.items())
        for i in range(len(ovals)):
            for j in range(i + 1, len(ovals)):
                (oa, ia), (ob, ib) = ovals[i], ovals[j]
                res = classify_pair(oa, ob)
                rec = {"key": key, "obj_a": oa, "obj_b": ob,
                       "category": res["category"],
                       "receipt_a": ia.get("span_id"), "receipt_b": ib.get("span_id"),
                       "session_a": ia.get("session"), "session_b": ib.get("session"),
                       "rci": res.get("rci")}
                if res["category"] == UPDATE:
                    alerts.append(rec)
                elif res["category"] == MULTI_VALUE:
                    multivalue.append(rec)
                else:
                    noise.append(rec)
    return {"alerts": alerts, "multivalue": multivalue, "noise": noise}


def run_two_path(spans, extractor):
    """spans: [(span_id, session, text)]. Returns comparison candidates and the
    contradiction result. The assertion path is gate.assess (unchanged) and is
    not recomputed here; this measures the comparison path in isolation."""
    sc = Scope()
    candidates = []
    for span_id, session, text in spans:
        for tr in extractor(text):
            sc.observe(tr)
    # second pass so orbit is populated before scope decisions
    for span_id, session, text in spans:
        for tr in extractor(text):
            cand, _ = comparison_candidate(text, tr)
            if cand and sc.in_scope(tr[0]):
                cand.update(span_id=span_id, session=session)
                candidates.append(cand)
    return candidates, detect_contradictions(candidates)
