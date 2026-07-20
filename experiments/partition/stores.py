"""E7 the four partitioning conditions. Same facts, same encoder, same gate.

Every condition is built from ONE shared pair of registries, so the codebook,
the whitened item vectors and the registry size N are byte-identical across
conditions. The only thing that differs is which facts land in which
superposition — i.e. k per store. This is what makes the comparison a
partitioning experiment rather than four different memories.

  COND-0   'none'             one store, every fact.               key = ()
  COND-R   'relation'         one store per relation label.        key = (r,)
  COND-E   'entity'           one store per subject entity.        key = (s,)
  COND-RE  'entity_relation'  one store per (subject, relation).   key = (s, r)

ROUTING IS A SYMBOLIC DICTIONARY LOOKUP on the explicit labels the fact was
written with, and on the explicit labels the query is posed with. There is no
similarity, no inference, no learning about which store to probe. The
abstraction was performed by whoever wrote the fact; the substrate is not
asked to discover it. This is why partitioning does not smuggle in
second-order structure the substrate is not entitled to.

EMPTY CELLS (decided with the registrant, notebook entry 24): a routed cell
that holds no facts is created LAZILY as an empty Memory and probed normally.
write_path.query already handles k == 0 and returns a well-defined abstain
opinion, so every condition runs the identical code path and no condition
gets a free structural-abstention channel the baseline cannot have. The
structural-miss rate is logged separately so its contribution stays visible.

WRITES USE echo=False. The echo-check would reject writes at high load, so a
saturated COND-0 would end up holding FEWER facts than COND-RE and the
conditions would no longer be comparable. echo is an existing parameter of
the frozen write path, not new machinery. The fraction that WOULD have been
rejected is measured separately (echo_reject_rate) as a diagnostic.
"""

import os
import sys

_R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (_R, f"{_R}/substrate", f"{_R}/gate", f"{_R}/encoder", f"{_R}/mouth"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np

from registry import Registry
from write_path import Memory, default_calibration

from corpus import ALL_RELS, registry_names

CONDITIONS = ("COND-0", "COND-R", "COND-E", "COND-RE")
MODE_OF = {"COND-0": "none", "COND-R": "relation",
           "COND-E": "entity", "COND-RE": "entity_relation"}

_KEYFN = {
    "none": lambda s, r: (),
    "relation": lambda s, r: (r,),
    "entity": lambda s, r: (s,),
    "entity_relation": lambda s, r: (s, r),
}


class Partition:
    """A partitioned memory: dict of routing-key -> frozen Memory."""

    def __init__(self, name, mode, ent, rel, calib):
        assert mode in _KEYFN
        self.name, self.mode = name, mode
        self.ent, self.rel, self.calib = ent, rel, calib
        self.keyfn = _KEYFN[mode]
        self.stores = {}
        self.n_structural_miss = 0
        self.n_routed = 0

    def _store(self, key, create=True):
        m = self.stores.get(key)
        if m is None and create:
            m = Memory(self.ent, self.rel, calib=self.calib)
            self.stores[key] = m
        return m

    def load(self, facts):
        for f in facts:
            self._store(self.keyfn(f.subj, f.rel)).write(
                f.subj, f.rel, f.obj, echo=False)
        return self

    # ------------------------------------------------------------- read side

    def route(self, subj, rel):
        """Symbolic lookup. Returns (Memory, existed_before). A miss creates
        an empty store and is counted, not short-circuited."""
        key = self.keyfn(subj, rel)
        existed = key in self.stores
        self.n_routed += 1
        if not existed:
            self.n_structural_miss += 1
        return self._store(key), existed

    def query(self, subj_term, rel_term):
        """The frozen read path, on the routed sub-store."""
        mem, existed = self.route(subj_term, rel_term)
        return mem.query(subj_term, rel_term), mem, existed

    def unbind_top1(self, mem, subj_term, rel_term):
        """Raw cleanup geometry from the SAME unbind the gate saw: (a, m,
        top1). Resolution through the registry exactly as query() does."""
        subj = self.ent.resolve(subj_term, top=2)[0][0]
        r = self.rel.resolve(rel_term, top=2)[0][0]
        if mem.k == 0:
            return 0.0, 0.0, None
        a, m, top1 = mem._unbind(subj, r)
        return float(a), float(m), top1

    # ------------------------------------------------------------ statistics

    def k_distribution(self):
        ks = sorted(m.k for m in self.stores.values())
        v = np.asarray(ks) if ks else np.array([0])
        return {
            "n_stores": len(self.stores),
            "k_mean": float(v.mean()), "k_median": float(np.median(v)),
            "k_p90": float(np.percentile(v, 90)), "k_max": int(v.max()),
            "frac_stores_multifact": float(np.mean(v > 1)),
            "total_facts": int(v.sum()),
        }


def build_conditions(world, cfg, calib=None):
    """All four conditions over one world's facts, on shared registries."""
    ent = Registry(registry_names(cfg, world))
    rel = Registry(ALL_RELS)
    calib = calib if calib is not None else default_calibration()
    parts = {}
    for name in CONDITIONS:
        parts[name] = Partition(name, MODE_OF[name], ent, rel, calib).load(world.facts)
    return parts, ent, rel


def echo_reject_rate(world, cfg, ent, rel, calib, sample=200, seed=0):
    """Diagnostic only: what fraction of writes the frozen echo-check WOULD
    have rejected in the unpartitioned store. Not used to filter facts —
    all conditions hold the identical fact set by construction."""
    rng = np.random.default_rng(seed)
    mem = Memory(ent, rel, calib=calib)
    for f in world.facts:
        mem.write(f.subj, f.rel, f.obj, echo=False)
    idx = rng.permutation(len(world.facts))[:sample]
    bad = 0
    for i in idx:
        f = world.facts[i]
        a, _, top1 = mem._unbind(ent.resolve(f.subj, top=1)[0][0],
                                 rel.resolve(f.rel, top=1)[0][0])
        if top1 != f.obj:
            bad += 1
    return bad / max(1, len(idx))
