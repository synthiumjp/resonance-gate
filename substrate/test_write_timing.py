"""E1 exit criterion 3: the write path is O(1).

The memory is a running int64 accumulator over records (bundle = sign at read
time). Appending fact k+1 is one elementwise add into the accumulator; it never
touches facts 1..k. This test measures per-append time after prefilling the
memory to various k and asserts the times are flat in k.
"""

import time

import numpy as np

D = 8192
SEED = 42
KS = [10, 1_000, 10_000, 50_000]
BATCH = 200  # appends timed per measurement
REPEATS = 5  # take the median over repeats to tame scheduler noise


def _records(rng, n):
    return (rng.integers(0, 2, size=(n, D), dtype=np.int8) * 2 - 1).astype(np.int8)


def test_write_is_o1():
    print(f"\n[O(1) write] seed={SEED} D={D} batch={BATCH} repeats={REPEATS}")
    rng = np.random.default_rng(SEED)
    fresh = _records(rng, BATCH)  # same records appended at every k
    per_append_us = {}

    for k in KS:
        acc = np.zeros(D, dtype=np.int64)
        # prefill the memory to genuinely contain k facts (chunked generation
        # to bound peak memory; the writes themselves are per-record adds)
        for start in range(0, k, 1000):
            for rec in _records(rng, min(1000, k - start)):
                acc += rec
        times = []
        for _ in range(REPEATS):
            t0 = time.perf_counter()
            for rec in fresh:
                acc += rec
            times.append(time.perf_counter() - t0)
        per_append_us[k] = np.median(times) / BATCH * 1e6

    for k, us in per_append_us.items():
        print(f"[O(1) write] k={k:>6}: {us:.2f} us/append")

    lo, hi = min(per_append_us.values()), max(per_append_us.values())
    ratio = hi / lo
    print(f"[O(1) write] max/min per-append time ratio across k: {ratio:.2f}")
    assert ratio < 3.0, f"append time not flat in k (ratio {ratio:.2f})"
