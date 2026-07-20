"""E8 per-hop instrumented traversal.

Symbolic-reference traversal, identical in policy to E7: the chain
[subj, r1, r2, r3] is held in ordinary Python outside the geometry, each hop
is a single first-order probe of the frozen read path, the result is cleaned
to an exact codebook entry, and that exact symbol launches the next hop.
FORCE-CONTINUE on top-1 throughout.

The per-hop record is the point of this experiment. For every hop we log the
raw geometry (a, m), the full opinion (b, d, u) with the winning d-source
tag, the routed action, and -- from corpus ground truth, not from the store --
whether that hop was STRUCTURALLY UNDERDETERMINED (its key carries more than
one valid object). That last field is what lets a confidence collapse be
localised to the fan-out hop rather than merely observed somewhere in the
chain.

TWO SCORINGS, reported separately because they answer different questions:
  ANY-VALID   every hop landed on some legal object for its key, and the
              chain ended on a legal final. "Can it traverse fan-out at all."
  SPECIFIC    the chain ended on the single designated target.
              "Can it pick the intended branch."
For functional chains the two coincide by construction.
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
    subj_term: object
    rel: str
    n_objects_at_key: int   # structural cardinality from corpus ground truth
    underdetermined: bool
    a: float
    m: float
    top1: object
    b: float
    d: float
    u: float
    z: float
    tag: object             # winning d-source: referential / stored / ...
    action: str
    link_valid: object      # top1 in the legal object set for this key
    link_intended: object   # top1 == the intended-path object


@dataclass
class Traversal:
    chain: object
    hops: list = field(default_factory=list)
    answer: object = None
    correct_specific: bool = False
    correct_any_valid: bool = False
    all_hops_valid: bool = False
    conf_min_b: float = 0.0
    conf_prod_b: float = 0.0
    conf_min_1mu: float = 0.0
    conf_prod_1mu: float = 0.0


def run_chain(mem, chain):
    tr = Traversal(chain=chain)
    subj_term = chain.start

    for i, rel in enumerate(chain.rels):
        legal = chain.valid_at.get((i, subj_term), set())
        qr = mem.query(subj_term, rel)
        subj_res = mem.ent.resolve(subj_term, top=2)[0][0]
        rel_res = mem.rel.resolve(rel, top=2)[0][0]
        a, m, top1 = mem._unbind(subj_res, rel_res)

        intended_obj = (chain.intended_path[i + 1]
                        if subj_term == chain.intended_path[i] else None)
        tr.hops.append(Hop(
            index=i, subj_term=subj_term, rel=rel_res,
            n_objects_at_key=len(legal), underdetermined=len(legal) > 1,
            a=float(a), m=float(m), top1=top1,
            b=float(qr.op.b), d=float(qr.op.d), u=float(qr.op.u),
            z=float(qr.op.z), tag=qr.tag, action=qr.action,
            link_valid=(top1 in legal) if legal else None,
            link_intended=(top1 == intended_obj) if intended_obj else None))
        subj_term = top1

    tr.answer = tr.hops[-1].top1
    tr.correct_specific = bool(tr.answer == chain.intended_final)
    tr.correct_any_valid = bool(tr.answer in chain.valid_finals)
    tr.all_hops_valid = all(h.link_valid is True for h in tr.hops)

    b = np.array([h.b for h in tr.hops], dtype=np.float64)
    one_mu = np.array([1.0 - h.u for h in tr.hops], dtype=np.float64)
    tr.conf_min_b, tr.conf_prod_b = float(b.min()), float(b.prod())
    tr.conf_min_1mu, tr.conf_prod_1mu = float(one_mu.min()), float(one_mu.prod())
    return tr


def to_row(tr, condition, k):
    ch = tr.chain
    return {
        "condition": condition, "world": ch.world, "k": k,
        "fanout_hop": ch.fanout_hop, "F": ch.F, "symmetric": ch.symmetric,
        "key_card": list(ch.key_card),
        "answer": tr.answer, "intended_final": ch.intended_final,
        "n_valid_finals": len(ch.valid_finals),
        "correct_specific": tr.correct_specific,
        "correct_any_valid": tr.correct_any_valid,
        "all_hops_valid": tr.all_hops_valid,
        **{k2: getattr(tr, k2) for k2 in CONF_KEYS},
        "hop_detail": [
            {"i": h.index, "rel": h.rel, "n_objects_at_key": h.n_objects_at_key,
             "underdetermined": h.underdetermined, "a": h.a, "m": h.m,
             "b": h.b, "d": h.d, "u": h.u, "z": h.z, "tag": h.tag,
             "action": h.action, "link_valid": h.link_valid,
             "link_intended": h.link_intended}
            for h in tr.hops],
    }
