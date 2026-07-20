"""E7 traversal with symbolic assembly.

The REFERENCE is the query decomposed into its symbolic chain
[subj, r1, r2, r3]. It lives in ordinary Python, OUTSIDE the geometry.
Composition never happens in a superposition: each hop probes a single
sub-store for a single first-order fact, cleans up to an EXACT codebook
entry, and hands that exact symbol back to the reference, which launches the
next hop. The substrate is only ever asked first-order questions.

POLICY (unchanged from E6, notebook entry 23): FORCE-CONTINUE on top-1. The
next hop's subject is always the cleanup result, whatever the gate routed, so
broken-chain behaviour is measured rather than short-circuited by the router.
Every hop's action is logged, so a halt-at-first-non-ANSWER policy remains
recoverable as a derived statistic.

CHAIN CONFIDENCE: min and product over hops, of b and of (1-u); all four
carried, evaluate.py picks and logs why.
"""

import os
import sys
from dataclasses import dataclass, field

_R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (_R, f"{_R}/substrate", f"{_R}/gate", f"{_R}/encoder", f"{_R}/mouth"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np

CONF_KEYS = ("conf_min_b", "conf_prod_b", "conf_min_1mu", "conf_prod_1mu")


@dataclass
class Hop:
    index: int
    subj_term: str
    rel: str
    k_store: int        # facts in the routed sub-store (measurement D)
    store_existed: bool
    a: float
    m: float
    top1: object
    b: float
    d: float
    u: float
    z: float
    action: str
    tag: object
    correct_link: object


@dataclass
class Traversal:
    chain: object
    condition: str
    hops: list = field(default_factory=list)
    answer: object = None
    correct: bool = False
    conf_min_b: float = 0.0
    conf_prod_b: float = 0.0
    conf_min_1mu: float = 0.0
    conf_prod_1mu: float = 0.0

    @property
    def all_answered(self):
        return all(h.action == "answer" for h in self.hops)

    @property
    def first_non_answer(self):
        for h in self.hops:
            if h.action != "answer":
                return h.index
        return None


def run_chain(part, chain):
    """Chained first-order probes over one Chain, in one condition."""
    tr = Traversal(chain=chain, condition=part.name)
    subj_term = chain.start          # the symbolic reference, hop 0

    for i, rel in enumerate(chain.rels):
        if subj_term is None:        # previous hop resolved to nothing
            tr.hops.append(Hop(i, None, rel, 0, False, 0.0, 0.0, None,
                               0.0, 0.0, 1.0, 0.0, "abstain", None, None))
            continue

        qr, mem, existed = part.query(subj_term, rel)
        a, m, top1 = part.unbind_top1(mem, subj_term, rel)

        true_obj = chain.links[i][2] if chain.stored[i] else None
        correct_link = (top1 == true_obj) if chain.stored[i] else None

        tr.hops.append(Hop(
            index=i, subj_term=subj_term, rel=rel, k_store=int(mem.k),
            store_existed=bool(existed), a=a, m=m, top1=top1,
            b=float(qr.op.b), d=float(qr.op.d), u=float(qr.op.u),
            z=float(qr.op.z), action=qr.action, tag=qr.tag,
            correct_link=correct_link))

        # FORCE-CONTINUE: the exact cleaned-up symbol re-enters the reference
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


def probe_atomic(part, subj, rel, gold):
    """One standalone single-hop query — the Kumar probe unit.

    Reports RAW top-1 cleanup accuracy (the retrieval measurement) and,
    separately, whether the gate routed ANSWER (the routing measurement).
    """
    qr, mem, existed = part.query(subj, rel)
    a, m, top1 = part.unbind_top1(mem, subj, rel)
    return {
        "subj": subj, "rel": rel, "gold": gold, "top1": top1,
        "retrieved": bool(top1 == gold),
        "k_store": int(mem.k), "store_existed": bool(existed),
        "a": a, "m": m, "b": float(qr.op.b), "u": float(qr.op.u),
        "action": qr.action,
        "answered_correct": bool(qr.action == "answer" and top1 == gold),
    }


def to_row(tr):
    ch = tr.chain
    return {
        "condition": tr.condition, "arm": ch.arm, "hops": ch.hops,
        "world": ch.world, "gold": ch.gold, "answer": tr.answer,
        "correct": tr.correct, "all_answered": tr.all_answered,
        "first_non_answer": tr.first_non_answer,
        **{k: getattr(tr, k) for k in CONF_KEYS},
        "hop_detail": [
            {"i": h.index, "rel": h.rel, "k_store": h.k_store,
             "store_existed": h.store_existed, "a": h.a, "m": h.m,
             "top1": h.top1, "b": h.b, "d": h.d, "u": h.u, "z": h.z,
             "action": h.action, "tag": h.tag, "correct_link": h.correct_link}
            for h in tr.hops
        ],
    }
