"""Character LM (one-layer LSTM) in numpy.

The input projection of all positions is one GEMM and every time step is one
[rows, H] x [H, 4H] GEMM, so numpy's BLAS (Accelerate / OpenBLAS / MKL) does the
heavy work.  Weights come from convert.py (charlm_*.npz).  torch LSTM gate order
i, f, g, o.
"""
import numpy as np


def _sigmoid(a):
    a = np.negative(a)
    np.exp(a, out=a)
    a += 1.0
    np.reciprocal(a, out=a)
    return a


class NumpyCharLSTM:
    def __init__(self, path):
        with np.load(path) as z:
            self.emb = z["emb"]
            self.w_ih_t = np.ascontiguousarray(z["w_ih"].T)      # [D, 4H]
            self.w_hh_t = np.ascontiguousarray(z["w_hh"].T)      # [H, 4H]
            self.bias = z["bias"]
            self.h0 = z["h0"]
            self.c0 = z["c0"]
        self.H = self.w_hh_t.shape[0]

    def run(self, ids):
        """ids [B, L] int64 -> hidden states, time-major [L, B, H] float32"""
        B, L = ids.shape
        H = self.H
        x = self.emb[ids.T]                                       # [L, B, D]
        gx = (x.reshape(L * B, -1) @ self.w_ih_t + self.bias).reshape(L, B, 4 * H)
        h = np.broadcast_to(self.h0, (B, H)).copy()
        c = np.broadcast_to(self.c0, (B, H)).copy()
        out = np.empty((L, B, H), np.float32)
        wt = self.w_hh_t
        for t in range(L):
            a = gx[t]
            a += h @ wt
            i = _sigmoid(a[:, :H])
            f = _sigmoid(a[:, H:2 * H])
            g = np.tanh(a[:, 2 * H:3 * H])
            o = _sigmoid(a[:, 3 * H:])
            c *= f
            i *= g
            c += i
            h = np.tanh(c)
            h *= o
            out[t] = h
        return out
