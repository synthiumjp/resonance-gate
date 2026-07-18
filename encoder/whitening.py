"""E3.1 task 4 (fork b): shrinkage ZCA whitening of embeddings before
projection. e' = (1-lambda)*e_hat + lambda*W(e)_hat (unit-normalised
components; sign(P@e') is scale-invariant). W is fit once on the codebook
embedding distribution and saved (deterministic given the pool, gitignored)."""

import os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ZCA_PATH = os.path.join(HERE, "zca_384.npz")
ZCA_EPS = 1e-5


def fit_zca(E, eps=ZCA_EPS):
    """ZCA whitening from the embedding sample E (n, e_dim): returns (mu, W)
    with W = U diag(1/sqrt(w+eps)) U^T of the covariance."""
    mu = E.mean(axis=0)
    C = np.cov(E - mu, rowvar=False)
    w, U = np.linalg.eigh(C)
    W = (U * (1.0 / np.sqrt(np.maximum(w, 0) + eps))) @ U.T
    return mu.astype(np.float32), W.astype(np.float32)


def load_or_fit_zca(fit_embeddings=None, path=ZCA_PATH):
    if os.path.exists(path):
        z = np.load(path)
        return z["mu"], z["W"]
    if fit_embeddings is None:
        raise FileNotFoundError(f"{path} missing and no fit sample given")
    mu, W = fit_zca(fit_embeddings)
    np.savez_compressed(path, mu=mu, W=W)
    return mu, W


def _unit(X):
    n = np.linalg.norm(X, axis=1, keepdims=True)
    return X / np.where(n == 0, 1, n)


def blend_transform(mu, W, lam):
    """Embedding-space transform for the sweep: lambda=0 is bit-identical to
    the unwhitened E3 path (embeddings arrive unit-normalised)."""
    def transform(E):
        E = np.asarray(E, dtype=np.float32)
        if lam == 0.0:
            return E
        Ew = _unit((E - mu) @ W.T)
        return (1.0 - lam) * _unit(E) + lam * Ew
    return transform
