"""The interface layer of the two-geometry design (notebook entry 7).

A Registry maps strings -> raw embeddings -> exact substrate entries. Query
terms and extracted strings resolve HERE, by raw-embedding cosine — this is
the semantic space where generalization and referential ambiguity live. The
substrate item vector for each entry uses the WHITENED projection (lambda
chosen on envelope alone, entry 8); the two geometries never mix.
"""

import numpy as np

from e31_common import get_embeddings
from whitening import blend_transform, load_or_fit_zca
from embed import project_bipolar

D = 8192
LAMBDA_SUBSTRATE = 0.75  # chosen on envelope alone — measurement in entry 8


def _unit(X):
    n = np.linalg.norm(X, axis=1, keepdims=True)
    return X / np.where(n == 0, 1, n)


class Registry:
    """Entity or relation registry. resolve() is raw-cosine (interface
    geometry); .vector() is the whitened bipolar item vector (substrate
    geometry) for the same entry."""

    def __init__(self, names, d=D, lam=LAMBDA_SUBSTRATE):
        self.d = d
        self.lam = lam
        mu, W = load_or_fit_zca()
        self._transform = blend_transform(mu, W, lam)
        self.names = []
        self._E = np.zeros((0, 384), dtype=np.float32)   # raw, unit
        self._V = np.zeros((0, d), dtype=np.int8)        # whitened bipolar
        self._index = {}
        if names:
            self.add(list(names))

    def add(self, names):
        """Append new entries (the write path grows the registry O(1)/entry)."""
        new = [n for n in names if n not in self._index]
        if not new:
            return
        E = _unit(get_embeddings(new))
        V = project_bipolar(self._transform(get_embeddings(new)), self.d)
        self._E = np.vstack([self._E, E])
        self._V = np.vstack([self._V, V])
        for n in new:
            self._index[n] = len(self.names)
            self.names.append(n)

    def __len__(self):
        return len(self.names)

    def __contains__(self, name):
        return name in self._index

    def resolve(self, term, top=2):
        """[(entry, cosine)] by RAW embedding cosine, best first."""
        e = _unit(get_embeddings([term]))[0]
        cos = self._E @ e
        order = np.argsort(-cos)[:top]
        return [(self.names[i], float(cos[i])) for i in order]

    def m_ref(self, term):
        """Referential margin c1 - c2 (low = 'which one do you mean?')."""
        r = self.resolve(term, top=2)
        if len(r) < 2:
            return 1.0
        return r[0][1] - r[1][1]

    @classmethod
    def from_state(cls, names, E, V, d=D, lam=LAMBDA_SUBSTRATE):
        """Reconstruct a registry from persisted arrays WITHOUT re-embedding
        (product-p1 restart recovery). E = raw unit embeddings (n,384), V =
        whitened bipolar item vectors (n,d). The blend transform is still
        loaded (from the committed ZCA file, no model) so later add()s work."""
        r = cls([], d=d, lam=lam)
        r.names = list(names)
        r._E = np.asarray(E, dtype=np.float32).reshape(-1, 384)
        r._V = np.asarray(V, dtype=np.int8).reshape(-1, d)
        r._index = {n: i for i, n in enumerate(r.names)}
        return r

    def raw_vector(self, name):
        """Unit RAW embedding (interface geometry) for a registered entry.
        product-p0 addition (rg-1.1 collision fix): the semantic
        stored-collision detector compares (subject, relation) keys by raw
        embedding cosine, so it needs per-entry raw vectors without
        re-embedding the surface string. Rows of _E are already unit."""
        return self._E[self._index[name]]

    def vector(self, name):
        """Exact substrate item vector (whitened projection) for an entry."""
        return self._V[self._index[name]]

    def vectors(self, names):
        return self._V[[self._index[n] for n in names]]

    def matrix(self):
        return self._V
