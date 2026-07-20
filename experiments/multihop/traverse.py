"""E6 chained unbinding: resolve hop 1, feed the cleaned-up result into hop 2.

No new machinery. Each hop is exactly one call to the frozen read path
(write_path.Memory.query -> registry resolve -> whitened unbind -> two-source
gate -> tagged routing), plus a read of the same unbind's raw geometry
(Memory._unbind) so the per-hop resolution `a` and margin `m` can be logged
alongside the (b, d, u) opinion. Nothing is re-tuned and no threshold is new.

TRAVERSAL POLICY (decided with the operator before implementation, notebook
entry 23): FORCE-CONTINUE. The next hop's subject term is always the top-1
cleanup result, whatever the gate routed — ANSWER, DELIBERATE, RECOLLECT or
ABSTAIN. The gate is never allowed to short-circuit the chain.

Rationale: halting at the first non-ANSWER would make the BROKEN arm partly
tautological (the router refuses, so "confidence collapsed" by construction)
and would yield no data on what the geometry actually does past a break.
Because every hop's action IS logged, the halt-at-first-non-ANSWER policy is
recoverable from the same run as a derived statistic — see
evaluate.halt_policy(). Force-continue is strictly the more informative run.

CHAIN CONFIDENCE. Two compositions of the per-hop belief, both reported:
    min(b)      the weakest link — a chain is only as good as its worst hop
    prod(b)     independent-hop composition — decays geometrically with L
Secondaries min(1-u) / prod(1-u) are carried too, because E5.1 (entry 19)
found 1-u the better-ranking scalar of the frozen gate. evaluate.py picks the
better-calibrated composition on the measured AUROC and logs why.
"""

import os
import sys
from dataclasses import dataclass, field

_R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (_R, f"{_R}/substrate", f"{_R}/gate", f"{_R}/encoder", f"{_R}/mouth"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np


@dataclass
class Hop:
    index: int          # 0-based hop number
    subj_term: str      # what this hop was asked with (hop>0: previous top-1)
    subj_resolved: str  # registry entry the term resolved to
    rel: str
    a: float            # top-1 cleanup cosine (resolution)
    m: float            # top1 - top2 cleanup margin
    top1: str           # cleanup result — the symbol fed to the next hop
    b: float
    d: float
    u: float
    z: float
    tag: object         # d-source tag when DELIBERATE, else None
    action: str         # 'answer' | 'deliberate' | 'recollect' | 'abstain'
    correct_link: object  # True/False if this hop's true object is known, else None


@dataclass
class Traversal:
    chain: object
    hops: list = field(default_factory=list)
    answer: str = None       # hop-N cleanup result = the final answer
    correct: bool = False    # final answer == gold (False whenever gold is None)

    # chain-confidence compositions
    conf_min_b: float = 0.0
    conf_prod_b: float = 0.0
    conf_min_1mu: float = 0.0
    conf_prod_1mu: float = 0.0

    @property
    def all_answered(self):
        """True iff every hop routed ANSWER (the halt-policy survival test)."""
        return all(h.action == "answer" for h in self.hops)

    @property
    def first_non_answer(self):
        for h in self.hops:
            if h.action != "answer":
                return h.index
        return None


def run_chain(mem, chain):
    """Chained unbind over one Chain. Returns a Traversal."""
    tr = Traversal(chain=chain)
    subj_term = chain.start

    for i, rel in enumerate(chain.rels):
        # the frozen read path: gate opinion + routing for this hop
        qr = mem.query(subj_term, rel)

        # the same unbind's raw geometry, for the per-hop (a, m) log. Resolve
        # through the registry exactly as query() does so the keys match.
        subj_res = mem.ent.resolve(subj_term, top=2)[0][0]
        rel_res = mem.rel.resolve(rel, top=2)[0][0]
        a, m, top1 = mem._unbind(subj_res, rel_res)

        # ground truth for THIS link, when the link was actually stored
        true_obj = chain.links[i][2] if chain.stored[i] else None
        correct_link = (top1 == true_obj) if chain.stored[i] else None

        tr.hops.append(Hop(
            index=i, subj_term=subj_term, subj_resolved=subj_res, rel=rel_res,
            a=float(a), m=float(m), top1=top1,
            b=float(qr.op.b), d=float(qr.op.d), u=float(qr.op.u),
            z=float(qr.op.z), tag=qr.tag, action=qr.action,
            correct_link=correct_link,
        ))

        # FORCE-CONTINUE: the cleanup result becomes the next hop's subject
        subj_term = top1

    tr.answer = tr.hops[-1].top1 if tr.hops else None
    tr.correct = bool(chain.gold is not None and tr.answer == chain.gold)

    b = np.array([h.b for h in tr.hops], dtype=np.float64)
    one_mu = np.array([1.0 - h.u for h in tr.hops], dtype=np.float64)
    tr.conf_min_b = float(b.min())
    tr.conf_prod_b = float(b.prod())
    tr.conf_min_1mu = float(one_mu.min())
    tr.conf_prod_1mu = float(one_mu.prod())
    return tr


def run_world(world):
    """Traverse every chain in a built world."""
    return [run_chain(world.memory, ch) for ch in world.chains]


CONF_KEYS = ("conf_min_b", "conf_prod_b", "conf_min_1mu", "conf_prod_1mu")


def to_row(tr):
    """Flatten a Traversal for storage / evaluation."""
    ch = tr.chain
    return {
        "arm": ch.arm, "hops": ch.hops, "world": ch.world,
        "start": ch.start, "rels": list(ch.rels),
        "missing_hop": ch.missing_hop, "gold": ch.gold,
        "answer": tr.answer, "correct": tr.correct,
        "all_answered": tr.all_answered,
        "first_non_answer": tr.first_non_answer,
        **{k: getattr(tr, k) for k in CONF_KEYS},
        "hop_detail": [
            {"i": h.index, "rel": h.rel, "a": h.a, "m": h.m, "top1": h.top1,
             "b": h.b, "d": h.d, "u": h.u, "z": h.z, "tag": h.tag,
             "action": h.action, "correct_link": h.correct_link}
            for h in tr.hops
        ],
    }
