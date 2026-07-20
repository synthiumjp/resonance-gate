"""MemoryService: the four MCP operations over the rg-1.1 substrate, plus
local snapshot persistence. Returns plain JSON-able dicts, never prose.

No language model is used here beyond the registry's MiniLM ENCODER (a
deterministic string->vector map, loaded lazily only when a NOVEL string is
first written). No generation, no extraction, no inference of unstated facts.
"""

import json
import os
import threading

from rg_memory import substrate_path  # noqa: F401 — sys.path + offline env

import numpy as np

from registry import Registry, D
from write_path import Memory, PROVENANCE_ROLES
from l2_ambiguity import L2Store, relation_equiv, semantic_collision

# caller-facing provenance vocabulary (stored verbatim)
SOURCES = ("caller-stated", "user-stated", "agent-inferred", "tool-derived")
DEFAULT_SOURCE = "caller-stated"

# recall resolution floor: below this raw-embedding cosine to the nearest
# registered entity, the query does not name anything we know -> honest empty.
RECALL_RESOLVE_MIN = 0.60


def _rid(idx):
    return f"r{idx}"


def _idx(rid):
    return int(rid[1:]) if isinstance(rid, str) and rid.startswith("r") else int(rid)


class MemoryService:
    """Thread-safe wrapper: MCP tools and the browser share one instance."""

    def __init__(self, state_dir):
        self.state_dir = state_dir
        self.lock = threading.RLock()
        os.makedirs(state_dir, exist_ok=True)
        self.mem = self._load() or self._fresh()

    # ------------------------------------------------------------ lifecycle

    def _fresh(self):
        # empty registries; relations and entities are added on write. No
        # embedding happens until the first novel string is written.
        ent = Registry([])
        rel = Registry([])
        return Memory(ent, rel)

    def _snapshot_paths(self):
        d = self.state_dir
        return (os.path.join(d, "arrays.npz"), os.path.join(d, "state.json"))

    def _save(self):
        """Full atomic snapshot after every mutation (substrate is small)."""
        mem = self.mem
        npz, js = self._snapshot_paths()
        store = mem.store
        keys = (np.stack(store._keys).astype(np.int8) if store._keys
                else np.zeros((0, D), np.int8))
        arrays = {
            "ent_E": mem.ent._E, "ent_V": mem.ent._V,
            "rel_E": mem.rel._E, "rel_V": mem.rel._V,
            "acc": mem.acc, "store_keys": keys,
        }
        nm, hm = mem.nm, mem.hm
        meta = {
            "version": 1,
            "ent_names": mem.ent.names, "rel_names": mem.rel.names,
            "store_objs": store.objs,
            "store_meta": [{"provenance": m["provenance"],
                            "triple": list(m["triple"])} if m else None
                           for m in store.meta],
            "store_active": [bool(x) for x in store.active],
            "k": mem.k,
            "triple_index": [[s, r, o, i]
                             for (s, r, o), i in mem._triple_index.items()],
            "calib": {"nm": [float(nm[0]), float(nm[1])],
                      "hm": [float(hm[0]), list(map(float, hm[1])),
                             list(map(float, hm[2]))]},
        }
        with open(npz + ".tmp", "wb") as f:   # file obj: no .npz auto-suffix
            np.savez(f, **arrays)
        os.replace(npz + ".tmp", npz)
        with open(js + ".tmp", "w") as f:
            json.dump(meta, f)
        os.replace(js + ".tmp", js)

    def _load(self):
        npz, js = self._snapshot_paths()
        if not (os.path.exists(npz) and os.path.exists(js)):
            return None
        a = np.load(npz, allow_pickle=False)
        with open(js) as f:
            m = json.load(f)
        ent = Registry.from_state(m["ent_names"], a["ent_E"], a["ent_V"])
        rel = Registry.from_state(m["rel_names"], a["rel_E"], a["rel_V"])
        nm = tuple(m["calib"]["nm"])
        hm = (m["calib"]["hm"][0], np.array(m["calib"]["hm"][1]),
              np.array(m["calib"]["hm"][2]))
        mem = Memory(ent, rel, calib=(nm, hm))
        # restore store
        store = L2Store(D)
        keys = a["store_keys"]
        store._keys = [keys[i] for i in range(keys.shape[0])]
        store.objs = list(m["store_objs"])
        store.meta = [None if md is None else
                      {"provenance": md["provenance"],
                       "triple": tuple(md["triple"])} for md in m["store_meta"]]
        store.active = [bool(x) for x in m["store_active"]]
        mem.store = store
        mem.acc = a["acc"].astype(np.int64)
        mem.k = int(m["k"])
        mem._triple_index = {(s, r, o): i for s, r, o, i in m["triple_index"]}
        return mem

    # -------------------------------------------------------------- helpers

    def _active_records(self):
        """[(store_idx, (subj, rel, obj), provenance)] for active records."""
        out = []
        for i, md in enumerate(self.mem.store.meta):
            if self.mem.store.active[i] and md:
                out.append((i, md["triple"], md["provenance"]))
        return out

    def _confidence(self, subj, rel):
        q = self.mem.query(subj, rel)
        op = q.op
        return ({"b": round(float(op.b), 4), "d": round(float(op.d), 4),
                 "u": round(float(op.u), 4)}, q)

    def _fact(self, idx, triple, provenance, conf):
        s, r, o = triple
        return {"subject": s, "relation": r, "object": o, "source": provenance,
                "record_id": _rid(idx), "confidence": conf}

    # --------------------------------------------------------------- tools

    def remember(self, subject, relation, object, source=DEFAULT_SOURCE):
        if source not in SOURCES:
            return {"stored": False, "record_id": None, "echo_ok": False,
                    "error": f"source must be one of {list(SOURCES)}"}
        with self.lock:
            res = self.mem.write(subject, relation, object,
                                 provenance=source, echo=True)
            if not res.accepted:
                return {"stored": False, "record_id": None, "echo_ok": False,
                        "reason": res.reason}
            idx = self.mem._triple_index.get((subject, relation, object))
            self._save()
            return {"stored": True, "record_id": _rid(idx), "echo_ok": True}

    def recall(self, query, top_k=10):
        with self.lock:
            mem = self.mem
            if len(mem.ent) == 0:
                return {"resolved": False, "facts": [], "conflict": False}
            res = mem.ent.resolve(query, top=1)
            if not res or res[0][1] < RECALL_RESOLVE_MIN:
                return {"resolved": False, "facts": [], "conflict": False}
            subj = res[0][0]
            recs = [(i, t, p) for i, t, p in self._active_records()
                    if t[0] == subj]
            if not recs:
                return {"resolved": False, "facts": [], "conflict": False}

            # group by relation-equivalence class; one gate query per class
            # surfaces the whole class (incl. near-synonym collisions).
            classes = []  # list of (representative_rel, [ (idx,triple,prov) ])
            for i, t, p in recs:
                placed = False
                for cls in classes:
                    if relation_equiv(cls[0], t[1]):
                        cls[1].append((i, t, p))
                        placed = True
                        break
                if not placed:
                    classes.append((t[1], [(i, t, p)]))

            facts, any_conflict, hint = [], False, None
            for rep_rel, members in classes:
                conf, q = self._confidence(subj, rep_rel)
                objs = {t[2] for _, t, _ in members}
                is_conflict = bool(q.conflict) and len(objs) > 1
                for i, t, p in members:
                    facts.append(self._fact(i, t, p, conf))
                if is_conflict:
                    any_conflict = True
                    if hint is None and q.resolution_hint:
                        hint = self._hint_ids(members, q.resolution_hint)
            facts.sort(key=lambda f: f["confidence"]["b"], reverse=True)
            out = {"resolved": True, "facts": facts[:top_k],
                   "conflict": any_conflict}
            if any_conflict and hint:
                out["resolution_hint"] = hint
            return out

    def _hint_ids(self, members, resolution_hint):
        by_triple = {t: i for i, t, _ in members}
        def rid_for(tr):
            return _rid(by_triple[tr]) if tr in by_triple else None
        return {"by_recency": rid_for(resolution_hint["by_recency"]),
                "by_resolution": rid_for(resolution_hint["by_resolution"])}

    def update(self, subject, relation, object, source=DEFAULT_SOURCE):
        if source not in SOURCES:
            return {"updated": False, "new_record_id": None, "superseded": [],
                    "error": f"source must be one of {list(SOURCES)}"}
        with self.lock:
            mem = self.mem
            # supersede every active record for this subject under an
            # EQUIVALENT relation (resolves the whole conflict, as the caller
            # explicitly asked). Distinct from a passive collision.
            superseded = []
            for i, t, p in self._active_records():
                if t[0] == subject and relation_equiv(relation, t[1]):
                    if mem.forget(*t):
                        superseded.append(_rid(i))
            res = mem.write(subject, relation, object,
                            provenance=source, echo=True)
            if not res.accepted:
                # roll-forward failed; report honestly (old records already
                # tombstoned — this is a corrupt correction, surfaced not hidden)
                self._save()
                return {"updated": False, "new_record_id": None,
                        "superseded": superseded, "reason": res.reason}
            idx = mem._triple_index.get((subject, relation, object))
            self._save()
            return {"updated": True, "new_record_id": _rid(idx),
                    "superseded": superseded}

    def forget(self, subject, relation=None, object=None):
        with self.lock:
            mem = self.mem
            forgotten = []
            for i, t, p in self._active_records():
                if t[0] != subject:
                    continue
                if relation is not None and not relation_equiv(relation, t[1]):
                    continue
                if object is not None and t[2] != object:
                    continue
                if mem.forget(*t):
                    forgotten.append(_rid(i))
            if forgotten:
                self._save()
            return {"forgotten": forgotten}

    # --------------------------------------------------------- browser feed

    def all_records(self):
        """Every active record + conflict flag, for the read-only browser."""
        with self.lock:
            recs = self._active_records()
            # detect which records participate in a conflict
            conflicted = set()
            seen_keys = set()
            for i, t, p in recs:
                key = (t[0], t[1])
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                score, conflicts, _ = semantic_collision(
                    self.mem.store, self.mem.ent, self.mem.rel, t[0], t[1])
                if conflicts:
                    conflicted.add(i)
                    for tr, pv, ci, sc in conflicts:
                        conflicted.add(ci)
            out = []
            for i, t, p in recs:
                conf, _ = self._confidence(t[0], t[1])
                out.append({"record_id": _rid(i), "subject": t[0],
                            "relation": t[1], "object": t[2], "source": p,
                            "confidence": conf, "conflict": i in conflicted})
            out.sort(key=lambda r: (r["subject"], r["relation"]))
            return out
