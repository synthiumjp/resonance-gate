"""Synthetic-known-answer validation of the type-2 apparatus (no worked
example exists in docs/ — this test IS the validation of record)."""

import numpy as np
import pytest

from type2 import auroc2, ece, meta_d_prime, paired_bootstrap, pseudo_2afc


def simulate_observer(n, d_prime, meta_noise, seed):
    """Equal-variance SDT observer: evidence x ~ N(+-d'/2, 1); decision by
    sign; confidence from a meta-read of x corrupted by N(0, meta_noise).
    meta_noise=0 -> M-ratio ~ 1; larger -> lower."""
    rng = np.random.default_rng(seed)
    stim = rng.integers(2, size=n)                        # 0 -> mean -d/2
    x = rng.normal((stim * 2 - 1) * d_prime / 2, 1.0)
    resp = (x > 0).astype(int)
    correct = resp == stim
    x_meta = x + rng.normal(0, meta_noise, size=n)
    conf = np.abs(x_meta)
    return conf, correct


def test_auroc2_known_answer():
    rng = np.random.default_rng(7)
    n = 4000
    correct = rng.integers(2, size=n).astype(bool)
    conf = np.where(correct, rng.normal(1, 1, n), rng.normal(0, 1, n))
    # analytic AUC for two unit-variance normals 1 apart: Phi(1/sqrt(2)) = 0.760
    assert abs(auroc2(conf, correct) - 0.7602) < 0.02
    # degenerate confidence -> 0.5
    assert abs(auroc2(np.ones(n), correct) - 0.5) < 1e-9


def test_ece_known_answer():
    rng = np.random.default_rng(8)
    n = 20000
    conf = rng.uniform(0, 1, n)
    correct = rng.uniform(0, 1, n) < conf     # perfectly calibrated
    assert ece(conf, correct) < 0.02
    assert ece(np.full(n, 0.9), np.zeros(n, dtype=bool)) > 0.85  # maximally off


def test_pseudo_2afc_accuracy_matches_auroc2():
    conf, correct = simulate_observer(6000, 1.5, 0.0, seed=9)
    p = pseudo_2afc(conf, correct, seed=10)
    assert abs(p["acc"].mean() - auroc2(conf, correct)) < 0.02


def test_meta_d_recovers_ideal_observer():
    """meta_noise=0: the confidence read IS the decision variable, so
    M-ratio must recover ~1; meta_noise=1.5 must land clearly lower."""
    conf, correct = simulate_observer(8000, 1.8, 0.0, seed=11)
    r = meta_d_prime(conf, correct, seed=12)
    print(f"\n[type2] ideal observer: d'={r['d_prime']:.3f} meta-d'={r['meta_d']:.3f} "
          f"M={r['m_ratio']:.3f}")
    assert r["eligible"]
    assert abs(r["m_ratio"] - 1.0) < 0.15

    conf2, correct2 = simulate_observer(8000, 1.8, 1.5, seed=13)
    r2 = meta_d_prime(conf2, correct2, seed=14)
    print(f"[type2] noisy-meta observer: M={r2['m_ratio']:.3f}")
    assert r2["eligible"]
    assert r2["m_ratio"] < r["m_ratio"] - 0.2


def test_meta_d_exclusions_are_exclusions():
    rng = np.random.default_rng(15)
    # accuracy above window (0.99) -> ineligible, no force-fit
    conf, correct = simulate_observer(3000, 5.0, 0.0, seed=16)
    r = meta_d_prime(conf, correct, seed=17)
    assert not r["eligible"] and "window" in r["reason"]
    # chance observer: accuracy ~0.5 -> below window
    conf2 = rng.uniform(0, 1, 3000)
    correct2 = rng.integers(2, size=3000).astype(bool)
    r2 = meta_d_prime(conf2, correct2, seed=18)
    assert not r2["eligible"]


def test_paired_bootstrap_reports_and_ranks():
    conf, correct = simulate_observer(1500, 1.5, 0.0, seed=19)
    worse = conf + np.random.default_rng(20).normal(0, 2.0, len(conf))
    out = paired_bootstrap({"good": conf, "bad": worse}, correct, B=500, seed=21)
    assert out["B"] == 500 and out["seed"] == 21
    lo, hi = out["diff_ci"][("good", "bad")]
    print(f"\n[type2] paired diff CI good-bad: ({lo:.3f}, {hi:.3f})")
    assert lo > 0, "good source must beat bad with CI excluding zero"
    a, b = out["ci"]["good"]
    assert a < out["point"]["good"] < b
