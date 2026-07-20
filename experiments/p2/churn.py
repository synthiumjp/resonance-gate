"""p2 store-churn instrument: reliable change applied to the MEMORY STORE.

The idea from "Beyond the Mean" (Cacioli, arXiv:2604.27405) transferred from
model-version comparison to memory-over-time. There the finding is that an
aggregate accuracy gain is the net residual of opposing item-level movements
(items improving while others deteriorate). A memory store does the same thing:
between two points in time, some facts strengthen (revisited, corroborated),
some decay (dormant), some are superseded, some contradicted. Two stores with
identical aggregate "80% of facts still hold" can have completely different
churn underneath, and one is stable while the other is thrashing.

No memory system in the field reports this. They report a store size and maybe
an accuracy; none reports the item-level movement distribution. This is the
"beyond the mean" critique applied to memory, and strength.py already makes the
per-fact latent (strength) observable, so the movement is measurable.

WHAT THIS COMPUTES. Given a fact's strength trajectory across sessions, the
per-fact delta between two timepoints, then RCI over those deltas exactly as in
run_btm_analysis.py:
    SEM = SD_strength * sqrt(1 - r_xx)
    S_diff = sqrt(SEM_t0^2 + SEM_t1^2)
    RCI_fact = (strength_t1 - strength_t0) / S_diff
    reliable movement if |RCI| > 1.96
and reports the CHURN DECOMPOSITION:
    reliable_strengthened / reliable_weakened / stable
plus the headline "beyond the mean" numbers: net aggregate change, and the
opposing gross movements it is the residual of.

r_xx here is split-half over the per-session strength observations of the SAME
fact -- which IS available in this setting (unlike the single-observation probe
of entry 34), because a fact revisited across sessions has repeated strength
reads. This is the setting entry 34 said the RCI statistic actually needs.
"""

import math
import statistics as st
from collections import defaultdict

RCI_THRESHOLD = 1.96


def split_half_reliability(observations, n_splits=200):
    """Spearman-Brown-corrected split-half reliability of a set of repeated
    per-fact strength observations. Mirrors 'Beyond the Mean' §3.2 but over
    strength reads of one fact across sessions instead of trials of one item.

    Deterministic: splits are index-parity rotations, not RNG draws, because
    the workflow/runtime forbids Math.random-equivalents and because a fixed
    split is reproducible. With few observations this is coarse; reported with
    n so the caller can discount it."""
    obs = list(observations)
    if len(obs) < 4:
        return None                         # not estimable; caller must handle
    corrs = []
    for shift in range(min(n_splits, len(obs))):
        idx = list(range(len(obs)))
        idx = idx[shift:] + idx[:shift]
        a = [obs[i] for i in idx[0::2]]
        b = [obs[i] for i in idx[1::2]]
        m = min(len(a), len(b))
        if m < 2:
            continue
        a, b = a[:m], b[:m]
        if st.pstdev(a) == 0 or st.pstdev(b) == 0:
            corrs.append(1.0 if a == b else 0.0)
            continue
        try:
            r = st.correlation(a, b)
        except Exception:
            continue
        corrs.append(max(-1.0, min(1.0, r)))
    if not corrs:
        return None
    r_hh = sum(corrs) / len(corrs)
    # Spearman-Brown for full-length reliability from a half-length correlation
    return max(0.0, min(1.0, 2 * r_hh / (1 + r_hh)))


class ChurnMeter:
    """Records each fact's strength at each session it is observed, then
    reports the reliable-change decomposition of the store between two
    session cut-points."""

    def __init__(self):
        # fact_key -> list of (session, strength)
        self.trajectory = defaultdict(list)

    def observe(self, fact_key, session, strength):
        self.trajectory[fact_key].append((int(session), float(strength)))

    def _strength_at(self, traj, cut):
        """Strength as of session <= cut: the last observation at or before the
        cut, or None if the fact had not appeared yet."""
        seen = [s for (sess, s) in traj if sess <= cut]
        return seen[-1] if seen else None

    def churn(self, t0, t1, global_reliability=None):
        """Reliable-change decomposition of the store between sessions t0 and t1.

        global_reliability: r_xx for facts with too few observations to estimate
        their own; if None, computed as the mean of the estimable per-fact
        reliabilities (a pooled fallback)."""
        # SD of strength across the store at t0, for SEM
        s0_all = [self._strength_at(v, t0) for v in self.trajectory.values()]
        s1_all = [self._strength_at(v, t1) for v in self.trajectory.values()]
        present = [(a, b) for a, b in zip(s0_all, s1_all) if a is not None and b is not None]
        if len(present) < 2:
            return {"n": len(present), "insufficient": True}
        sd0 = st.pstdev([a for a, _ in present])
        sd1 = st.pstdev([b for _, b in present])

        # RELIABILITY. Split-half over a fact's strength trajectory measures
        # the curve's autocorrelation, not the extractor's reliability (entry
        # 35 caught this: it inflated r_xx to ~0.8 on smooth decay curves). A
        # valid r_xx needs repeated EXTRACTIONS of the same span, which we do
        # not have. So r_xx is taken as a fixed, explicit input, defaulting to
        # the held-out gate discriminability re-expressed as a reliability:
        # AUROC 0.882 (entry 31) -> r_xx ~= 0.55 via 2*AUROC-1 (a documented,
        # conservative stand-in, NOT a measured test-retest coefficient).
        per_fact_r = {}
        pooled = global_reliability if global_reliability is not None else 0.55

        rows, deltas = [], []
        strengthened = weakened = stable = 0
        gross_up = gross_down = 0.0
        for k, traj in self.trajectory.items():
            a = self._strength_at(traj, t0)
            b = self._strength_at(traj, t1)
            if a is None or b is None:
                continue
            r_xx = per_fact_r.get(k, pooled)
            sem0 = sd0 * math.sqrt(max(0.0, 1 - r_xx))
            sem1 = sd1 * math.sqrt(max(0.0, 1 - r_xx))
            s_diff = math.sqrt(sem0 ** 2 + sem1 ** 2)
            delta = b - a
            deltas.append(delta)
            rci = delta / s_diff if s_diff > 0 else (0.0 if delta == 0 else math.inf)
            if rci > RCI_THRESHOLD:
                strengthened += 1
                gross_up += delta
            elif rci < -RCI_THRESHOLD:
                weakened += 1
                gross_down += delta
            else:
                stable += 1
            rows.append({"fact": list(k), "delta": delta, "rci": rci})

        n = len(deltas)
        net = sum(deltas)
        return {
            "n": n, "t0": t0, "t1": t1,
            "reliable_strengthened": strengthened,
            "reliable_weakened": weakened,
            "stable": stable,
            "churn_rate": (strengthened + weakened) / n if n else float("nan"),
            # the "beyond the mean" headline: the net is the residual of these
            "net_strength_change": net,
            "gross_upward": gross_up,
            "gross_downward": gross_down,
            "mean_reliability": pooled,
            "n_facts_with_own_reliability": len(per_fact_r),
            "rows": sorted(rows, key=lambda r: r["rci"]),
        }
