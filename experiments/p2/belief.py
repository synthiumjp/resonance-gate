"""p2 Bayesian belief memory: a fact is a POSTERIOR, not a record.

The reframe (registrant, this session). Trust is not exposing uncertainty --
it is REMOVING it. So the memory does the inference internally and asserts only
what it has resolved. The uncertainty is the engine, not the interface.

This is not a database of growing facts. Each (subject, attribute) slot holds a
BELIEF: a posterior over candidate values. A mention is EVIDENCE that updates
the posterior. The state concentrates (gets sharper), it does not accumulate
(get bigger). Old evidence decays under a change-point prior, so a genuinely
changed value takes over while stale evidence fades.

It unifies what p2 built piecemeal:
  - write-gate/extraction confidence  -> the LIKELIHOOD of a piece of evidence
  - corroboration / survival          -> independent evidence, posterior concentrates
  - RCI change detection              -> the change-point prior (decay of old evidence)
  - commensurability                  -> defines what shares a slot vs a value
  - calibrated confidence             -> IS the posterior
  - abstention                        -> posterior entropy too high -> do not assert
  - store churn                       -> posterior dynamics over time

WEIGHT OF EVIDENCE (Good, 1950; the log-odds form of Bayes). A mention of value
v with extraction reliability r contributes weight-of-evidence
    w = log(r / (1 - r))
to v's log-posterior. Independent mentions ADD (that is Bayes in log-odds), so
corroboration concentrates the posterior automatically, and a single junk
mention (isolated, low r) never crosses the assertion threshold. r is grounded
in the measured extraction precision (p2 held-out ~0.64) and the per-mention
gate confidence, NOT invented.

THE ONE HONEST HARD PART, flagged not hidden: the likelihood r and the change
prior (decay rate) must be GROUNDED or this is Bayesian-flavoured hand-waving.
r comes from the measured gate precision; the decay is set from the observed
inter-mention session gap and must be fit against a labelled update/no-update
set before any calibration claim -- unfit here, defaults stated.

No model call in the belief update itself (the LLM only proposes evidence).
"""

import math
from collections import defaultdict

# defaults, STATED and unfit. r: measured p2 held-out gate precision.
DEFAULT_RELIABILITY = 0.64
# change-point: fraction of a value's evidence that remains relevant one
# "session-step" later. <1 lets a newer corroborated value overtake an older
# one (update) while a one-off does not. Unfit; a placeholder for a fitted rate.
EVIDENCE_RETENTION = 0.85
# JUNK PRIOR: base-rate probability that a single extracted (subject,attr,value)
# is a TRUE current fact rather than extraction noise. p2 measured ~90% junk on
# real turns, so ~0.10. This is the null hypothesis each value must overcome:
# one mention is not enough; evidence must accumulate. GROUNDED, not invented.
JUNK_PRIOR = 0.50   # POST-GATE prior: the gate already removed junk, so the
                    # belief starts near-neutral; corroboration and per-mention
                    # GATE CONFIDENCE (not a flat rate) drive it from here.
# assert a value once P(true) crosses this; flag a concurrent rival above the
# contradiction threshold.
ASSERT_PROB = 0.70
CONTRADICTION_PROB = 0.40


def _prior_log_odds(base=JUNK_PRIOR):
    return math.log(base / (1 - base))


def _sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))


def weight_of_evidence(reliability):
    r = min(max(reliability, 1e-4), 1 - 1e-4)
    return math.log(r / (1 - r))


class Belief:
    """Per-value log-odds that each value is the TRUE CURRENT value of one
    (subject, attribute) slot. Each value starts at the junk-prior log-odds and
    accrues weight of evidence; P(true) = sigmoid(log-odds). Corroboration is
    thus NECESSARY to cross belief -- a single mention sits near the junk prior."""

    def __init__(self):
        self.lo = defaultdict(_prior_log_odds)   # value -> log-odds of being true-current
        self.last_step = defaultdict(lambda: None)   # last REAL mention step
        self._decayed_to = defaultdict(lambda: None) # step lo was last decayed to
        self.n_evidence = defaultdict(int)

    def observe(self, value, step, reliability=DEFAULT_RELIABILITY,
                retention=EVIDENCE_RETENTION):
        self._decay_to(step, retention)
        self.lo[value] += weight_of_evidence(reliability)
        self.last_step[value] = step
        self.n_evidence[value] += 1

    def _decay_to(self, step, retention):
        # decay the EVIDENCE (log-odds above the prior) back toward the junk
        # prior for values not restated: a stale value reverts to "probably not
        # current". This is the change-point term.
        prior = _prior_log_odds()
        for v in list(self.lo):
            ref = self._decayed_to[v] if self._decayed_to[v] is not None else self.last_step[v]
            if ref is not None and step > ref:
                gap = step - ref
                self._decayed_to[v] = step
                # decay the belief toward the prior WITHOUT moving last_step:
                # last_step records the last real mention, so 'concurrent
                # conflict' (contradiction) stays distinguishable from 'old
                # value faded' (update).
                self.lo[v] = prior + (self.lo[v] - prior) * (retention ** gap)

    def prob(self, value):
        return _sigmoid(self.lo[value])

    def posterior(self):
        """P(true-current) per value -- NOT normalised to sum 1 (values are not
        mutually exclusive a priori; the junk hypothesis absorbs the rest)."""
        return {v: _sigmoid(l) for v, l in self.lo.items()}

    def top(self):
        p = self.posterior()
        return max(p.items(), key=lambda kv: kv[1]) if p else (None, 0.0)


class BeliefMemory:
    """The belief state: slots -> Belief. Asserts only concentrated posteriors;
    flags a slot whose posterior is split between concurrent rivals."""

    def __init__(self, reliability=DEFAULT_RELIABILITY, retention=EVIDENCE_RETENTION):
        self.slots = defaultdict(Belief)
        self.reliability = reliability
        self.retention = retention

    def observe(self, subject, attribute, value, step, reliability=None):
        self.slots[(subject, attribute)].observe(
            value, step, reliability or self.reliability, self.retention)

    def assertions(self, min_prob=ASSERT_PROB):
        """What the memory will STATE: slots where one value's P(true-current)
        has crossed the belief threshold. A one-off mention sits at the junk
        prior (~0.10) and is NOT asserted -- corroboration earned the belief.
        This is the trust surface: uncertainty resolved."""
        out = []
        for key, b in self.slots.items():
            v, prob = b.top()
            if v is not None and prob >= min_prob:
                out.append({"subject": key[0], "attribute": key[1], "value": v,
                            "confidence": prob, "n_evidence": b.n_evidence[v]})
        return out

    def conflicts(self, top_prob=CONTRADICTION_PROB, gap_lt=2):
        """Slots the memory will NOT silently resolve: two values BOTH above the
        contradiction probability whose last evidence is CONCURRENT (within
        `gap_lt` steps). Both believed now = a genuine contradiction, distinct
        from an UPDATE, where the old value's probability has decayed below
        threshold."""
        out = []
        for key, b in self.slots.items():
            p = sorted(b.posterior().items(), key=lambda kv: -kv[1])
            if len(p) >= 2 and p[0][1] >= top_prob and p[1][1] >= top_prob:
                (v1, m1), (v2, m2) = p[0], p[1]
                if abs((b.last_step[v1] or 0) - (b.last_step[v2] or 0)) < gap_lt:
                    out.append({"subject": key[0], "attribute": key[1],
                                "values": [(v1, m1), (v2, m2)], "kind": "contradiction"})
        return out

    def history(self, subject, attribute):
        """For an UPDATE, the superseded value(s) are still in the belief with
        decayed mass -- so 'you said X, now Y' is reconstructable with receipts,
        without keeping a growing log."""
        b = self.slots.get((subject, attribute))
        return sorted(b.posterior().items(), key=lambda kv: b.last_step[kv[0]] or 0) if b else []
