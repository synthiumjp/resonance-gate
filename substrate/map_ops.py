"""MAP algebra for the RG substrate (E1 spec in CLAUDE.md — fixed, do not redesign).

Bipolar int8 vectors in {-1,+1}. bind is elementwise product (self-inverse),
permute is np.roll, bundle is sign(sum) with seeded tie-break.
Record: R = subj * permute(rel, 1) * permute(obj, 2).
"""

import numpy as np

DEFAULT_D = 8192


class Codebook:
    """Named random bipolar item vectors (int8), seeded, with cosine cleanup."""

    def __init__(self, names, dim=DEFAULT_D, seed=0):
        self.names = list(names)
        if len(set(self.names)) != len(self.names):
            raise ValueError("codebook names must be unique")
        self.dim = dim
        self.seed = seed
        rng = np.random.default_rng(seed)
        self.matrix = (rng.integers(0, 2, size=(len(self.names), dim), dtype=np.int8) * 2 - 1).astype(np.int8)
        self._index = {n: i for i, n in enumerate(self.names)}

    def __getitem__(self, name):
        return self.matrix[self._index[name]]

    def __len__(self):
        return len(self.names)

    def cleanup(self, v, top_k=2):
        """Cosine of v against all items; return top_k [(name, cos)] sorted desc.

        The sorted cosines are load-bearing: a = s1 (resolution), m = s1 - s2
        (margin) for the default top_k=2.
        """
        cos = self.cosines(v)
        order = np.argsort(-cos)[:top_k]
        return [(self.names[i], float(cos[i])) for i in order]

    def cosines(self, v):
        """Cosine of v against every codebook row, in codebook order."""
        v = np.asarray(v, dtype=np.float32)
        vnorm = np.linalg.norm(v)
        if vnorm == 0:
            return np.zeros(len(self.names), dtype=np.float32)
        # rows are bipolar, so each row norm is sqrt(dim)
        return (self.matrix.astype(np.float32) @ v) / (np.sqrt(self.dim) * vnorm)


def bind(a, b):
    """Elementwise product; self-inverse on bipolar vectors."""
    return (a.astype(np.int8) * b.astype(np.int8)).astype(np.int8)


def permute(v, k):
    """Cyclic shift by k; inverse is permute(v, -k)."""
    return np.roll(v, k)


def bundle(vectors, seed=0):
    """sign(sum) of the stack; zero ties broken by a seeded coin (deterministic)."""
    s = np.sum(np.stack(vectors).astype(np.int64), axis=0)
    out = np.sign(s).astype(np.int8)
    ties = out == 0
    n_ties = int(ties.sum())
    if n_ties:
        rng = np.random.default_rng(seed)
        out[ties] = (rng.integers(0, 2, size=n_ties, dtype=np.int8) * 2 - 1).astype(np.int8)
    return out


def encode_record(subj, rel, obj):
    """R = subj * permute(rel, 1) * permute(obj, 2)."""
    return bind(subj, bind(permute(rel, 1), permute(obj, 2)))


def unbind_obj(B, subj, rel):
    """Noisy obj from B given (subj, rel): permute(B * subj * permute(rel,1), -2)."""
    return permute(bind(bind(B, subj), permute(rel, 1)), -2)


def unbind_subj(B, rel, obj):
    """Noisy subj from B given (rel, obj)."""
    return bind(bind(B, permute(rel, 1)), permute(obj, 2))


def unbind_rel(B, subj, obj):
    """Noisy rel from B given (subj, obj): permute(B * subj * permute(obj,2), -1)."""
    return permute(bind(bind(B, subj), permute(obj, 2)), -1)
