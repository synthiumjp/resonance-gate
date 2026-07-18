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
_P = None


def projection(path=PROJECTION_PATH, d=D, e_dim=EMBED_DIM, seed=PROJECTION_SEED):
    """The fixed random projection, drawn once and persisted (regenerable
    bit-exactly from the seed, hence gitignored)."""
    global _P
    if _P is None:
        if os.path.exists(path):
            _P = np.load(path)
            assert _P.shape == (d, e_dim), f"stale projection file {path}"
        else:
            _P = np.random.default_rng(seed).standard_normal((d, e_dim)).astype(np.float32)
            np.save(path, _P)
    return _P


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


def encode_bipolar(strings):
    """Strings -> bipolar int8 item vectors: sign(P @ embed(s)).
    Exact zeros (measure-zero under the Gaussian projection) map to +1."""
    e = embed_strings(strings)
    x = e @ projection().T
    v = np.where(x >= 0, 1, -1).astype(np.int8)
    return v


def build_codebook(names):
    """Embedded codebook: cleanup/algebra identical to the synthetic path."""
    from map_ops import Codebook
    return Codebook.from_matrix(names, encode_bipolar(names))
