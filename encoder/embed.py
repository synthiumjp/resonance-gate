"""E3 embedding path: entity/relation strings -> bipolar item vectors.

Pipeline: sentence-transformer embedding -> fixed seeded random projection ->
sign. The projection matrix P (D x e_dim) is drawn ONCE from a seeded Gaussian
and saved to disk; sign(P @ e) is invariant to embedding norm. Model and
revision are pinned below (and in notebook entry 5); the substrate itself
stays numpy-only — this module is behind the `encoder` extra.
"""

import os
import numpy as np

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
EMBED_DIM = 384
D = 8192
PROJECTION_SEED = 314
PROJECTION_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), f"projection_{D}x{EMBED_DIM}.npy"
)

_model = None
_P = {}


def projection_path(d=D, e_dim=EMBED_DIM):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        f"projection_{d}x{e_dim}.npy")


def projection(d=D, e_dim=EMBED_DIM, seed=PROJECTION_SEED):
    """The fixed random projection for dimension d, drawn once and persisted
    (regenerable bit-exactly from the seed, hence gitignored). Same seed
    policy at every d (E3.1 adds the D=16384 arm)."""
    if d not in _P:
        path = projection_path(d, e_dim)
        if os.path.exists(path):
            _P[d] = np.load(path)
            assert _P[d].shape == (d, e_dim), f"stale projection file {path}"
        else:
            _P[d] = np.random.default_rng(seed).standard_normal((d, e_dim)).astype(np.float32)
            np.save(path, _P[d])
    return _P[d]


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_NAME, revision=MODEL_REVISION, device="cpu")
    return _model


def embed_strings(strings, batch_size=256):
    """Sentence embeddings, (n, EMBED_DIM) float32."""
    return np.asarray(
        _get_model().encode(
            list(strings), batch_size=batch_size, show_progress_bar=False,
            convert_to_numpy=True, normalize_embeddings=True,
        ),
        dtype=np.float32,
    )


def project_bipolar(e, d=D):
    """Embeddings -> bipolar int8 item vectors: sign(P @ e).
    Exact zeros (measure-zero under the Gaussian projection) map to +1."""
    x = np.asarray(e, dtype=np.float32) @ projection(d).T
    return np.where(x >= 0, 1, -1).astype(np.int8)


def encode_bipolar(strings, d=D):
    """Strings -> bipolar int8 item vectors via the embedding path."""
    return project_bipolar(embed_strings(strings), d)


def build_codebook(names, d=D):
    """Embedded codebook: cleanup/algebra identical to the synthetic path."""
    from map_ops import Codebook
    return Codebook.from_matrix(names, encode_bipolar(names, d))
