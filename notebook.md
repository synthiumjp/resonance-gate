# RG lab notebook (append-only)

## Entry 1 — 2026-07-18

Scope frozen per project plan v1. Decisions locked for phase E:
- Encoder: embedding-path encoder (frozen small transformer phrases gate-cleared
  content later; it is never a source of facts).
- Algebra: MAP per the substrate spec in CLAUDE.md — bipolar int8, D=8192
  (D=16384 comparison arm), bind = elementwise product (self-inverse),
  permute = np.roll, bundle = sign(sum) with seeded tie-break,
  record R = subj * permute(rel,1) * permute(obj,2).
- Primary hardware: PC / WSL2, CPU-only NumPy. Substrate being trivial on CPU
  is a design claim we are proving.

Rationale: fix the algebra and hardware envelope before E1 measurements so the
capacity curves feed the E2 load-normalised gate without a moving target.

Note: docs/rg-project-plan-v1.md was not present in the repo at scaffold time;
E1 spec and exit criteria taken from CLAUDE.md.

## Entry 2 — 2026-07-18

Built E1 substrate core:
- `substrate/map_ops.py`: Codebook (named bipolar int8 item vectors, seeded;
  cosine cleanup returning top-k (name, cos) — a = s1, m = s1 - s2), bind,
  permute, bundle (sign(sum), seeded coin on zero ties), encode_record,
  unbind_obj / unbind_subj / unbind_rel.
- `substrate/test_map_ops.py`: algebra invariants + E1 exit round-trip.
- `substrate/capacity_sweep.py`: exit criterion 2 → capacity_curves.csv.
- `substrate/test_write_timing.py`: exit criterion 3.

Seeds: tests use SEED=42 (round-trip codebooks 42/43/44, triple sampling 45,
bundle tie-break 46); sweep uses master seed 42 expanded via
np.random.SeedSequence.spawn (one child per k, 20 trial seeds each); timing
test seed 42. Reproduce everything from a clean checkout with:
`python -m pytest substrate/ -s && python substrate/capacity_sweep.py --seed 42`

Results (D=8192, rel pool 10):
- Round-trip (criterion 1): 50/50 correct. a mean 0.112, min 0.088; m mean
  0.083, min 0.055. PASS.
- Capacity (criterion 2, obj pool 500): accuracy 1.000 through k=100, 0.9725
  at k=200, then falls off a cliff — 0.776 at k=350 (first sampled k below
  0.95), 0.569 at k=500.
- Hit-vs-miss Cohen's d on a: 24.4 (k=10), 15.5 (k=25), 9.7 (k=50), 5.7
  (k=100), 2.8 (k=200), 1.5 (k=350), 0.96 (k=500).
- O(1) write (criterion 3): 3-4 us/append, max/min ratio 1.45 across
  k in {10, 1e3, 1e4, 5e4}. Flat. PASS.

Surprises / notes:
- a_miss is strikingly load-invariant: mean ~0.0335, sd ~0.004 at every k.
  The ignorance floor doesn't move; separation degrades only because a_hit
  sinks toward it (~1/sqrt(k) attenuation from bundling). So mu/sigma for the
  E2 gate only needs the hit-side curve as a function of load — the miss side
  is a fixed property of (D, codebook size).
- d(a) stays > 2.7 while accuracy is still >= 0.97 (k <= 200), i.e. resolution
  geometry cleanly carries the hit/miss (ignorance) signal across the whole
  usable operating range. But d < 1 at k=500: past saturation, raw a cannot
  carry the gate — load normalisation in E2 is mandatory, not optional.
- sd(a_hit) is roughly constant (~0.011) until saturation, then shrinks; the
  signal loss is a mean effect, not a variance explosion.

## Entry 3 — 2026-07-18 (planning-session analysis of the E1 curves)

Attributed to planning-session analysis of capacity_curves.csv:
- a_hit follows the analytic bundling attenuation mu_hit(k) = sqrt(2/(pi*k))
  (predicts 0.252 / 0.113 / 0.036 at k = 10 / 50 / 500 vs measured
  0.247 / 0.112 / 0.039).
- a_miss is NOT fundamental noise; it is an extreme-value statistic of the
  null: mu_null(N) ~= sqrt(2*ln(N)/D) (predicts ~0.037 at N~700, D=8192,
  matching the measured 0.0335 floor). It is load-invariant but rises with
  codebook size N.
- Closed-form capacity law: separability dies at k_max ~= D/(pi*ln(N)).
  At D=8192, N~700: ~400, matching the observed saturation.

Consequence for E2: normalise a against BOTH anchors — expected hit signal
mu_hit(k) and null floor mu_null(N); k and N are always known exactly because
the substrate wrote every item. Sigma terms taken empirically from the E1 CSV.

## Entry 4 — 2026-07-18 (E2 gate built and measured)

Built: gate/normalisation.py (z(a) against both anchors, capacity-law
helpers), gate/opinion.py ((b,d,u) mapping), gate/controller.py (v0
fixed-threshold policy), gate/test_gate.py (E2 exit tests a–d + analytic
validation), gate/test_controller.py. Test seeds: 202 (ignorance), 203
(ambiguity), 204 (drift), 205 (saturation), via SeedSequence.spawn.

Tunables chosen (exploratory — tune freely, log every change):
- z zero-point = variance-weighted hit/null crossing
  c = (mu_hit*sig_null + mu_null*sig_hit)/(sig_hit + sig_null), NOT the
  midpoint. Rationale: sig_hit ~ 2.7x sig_null, so the midpoint boundary
  would misclassify ~20% of hits at k=200; the weighted crossing tracks the
  equal-error threshold. This is the one design decision made during the
  build that wasn't in the plan text.
- THETA = 0.0 — z is already zeroed at the crossing; load-invariance means
  one theta for all (k, N).
- ALPHA = 1.0, BETA = 1.0 — unit slope per pooled sigma; distributions sit
  multiple sigma from the boundaries below the paging threshold, so nothing
  sharper is needed.
- paging safety fraction = 0.5 (paging_threshold = 0.5 * k_max = 210 at
  D=8192, N=500) — keeps the live bundle where same-theta acc > 0.92 and
  AUC > 0.97. Tunable; revisit when L2 exists.
- saturation gamma = 1.0 null-sd (k_sat = 344 at N=500).
- Controller: U_IGNORANT = 0.85, U_WEAK = 0.35, ambiguity = (d > b).

Results (all 18 tests green):
- Validation: analytic mu_hit within 0.0052 of the E1 curve at every k;
  mu_null(500) within 0.0055 of the measured floor (the known ~1 null-sd
  extreme-value overshoot; constant offset, tracks the N-slope).
- (a) Ignorance, N=500, same theta at every k: AUC(u) = 1.0000 / 1.0000 /
  0.9998 / 0.9792 at k = 10/50/100/200; same-theta balanced acc = 1.000 /
  1.000 / 0.994 / 0.923 (best achievable at k=200: 0.938 — theta is within
  0.015 of optimal without per-k tuning). Exit bar met.
- (b) *** C3 SPLIT, first measurement: AUC(d) = 0.9988 *** (50 planted
  collisions vs 250 clean hits at k_eff=70). d dominant on 90% of
  collisions, b dominant on 98.4% of clean hits, u ~ 0 on both (the gate
  correctly refuses to call ambiguity "ignorance"). Exit bar (0.90) cleared
  with room.
- (c) Drift: miss-anchor drift across N in {200, 700, 2000}: N-aware 0.42 z
  vs k-only 1.12 z (2.6x); N-aware acc-at-theta >= 0.996 at every N.
  Figure-ready CSV: gate/drift_comparison.csv. Note: AUC is identical
  between modes at fixed (k, N) — normalisation is monotone — so the drift
  is purely a calibration phenomenon, which is exactly how the threats
  register frames the attack.
- (d) Saturation: paging 210 < k_sat 344 < k_max 420 as the law predicts;
  AUC collapses 0.984 (k=200) -> 0.820 (k=420); at flagged loads the
  controller routes 100% of queries to RECOLLECT, never ANSWER.

Surprises:
- The variance-weighted crossing mattered more than expected (see above);
  midpoint normalisation would have failed the same-theta exit bar at k=200.
- k-only drift is directional: at N > N_ref misses drift TOWARD the
  boundary (u_miss 0.93 -> 0.82 as N goes 200 -> 2000), i.e. a growing
  codebook makes the un-normalised gate overconfident about ignorance —
  the dangerous direction. N-awareness is not cosmetic.
- Saturated-load b is not merely unreliable, it is actively misleading
  (margin normalisation collapses as mu_hit -> mu_null), which is why the
  flag must gate routing rather than any b-threshold.

## Entry 5 — 2026-07-18 (E3 Part 1: encoder-realism check — STOP RULE FIRED)

Built: encoder/embed.py (MiniLM -> seeded Gaussian projection -> sign;
model pinned: sentence-transformers/all-MiniLM-L6-v2 @ revision
1110a243fdf4706b3f48f1d95db1a4f5529b4d41, projection seed 314, D=8192,
projection saved to disk, gitignored/regenerable), encoder/entities.py
(seeded confusable entity families), encoder/test_null_floor.py,
encoder/test_embedded_gate.py; EMBEDDED mode added to gate/normalisation.py
(null_moments override + calibrate_null measured on the actual codebook;
analytic mode unchanged, both tested). Codebook.from_matrix added to
substrate/map_ops.py (additive constructor; algebra untouched). Seeds: 550
(null floor), 660 (embedded gate), 770 (diagnostics).

Null-floor measurement (THE test of the stage), N in {200, 700, 2000}:
- Pairwise cosines of projected non-identical entities: mean 0.156-0.186,
  sd ~0.095 (analytic: mean 0, sd 0.011 — NINE times wider), p99 ~0.45-0.47,
  max 0.71-0.81. The embedding geometry survives the sign(P@e) projection
  essentially intact.
- Leave-one-out max-over-codebook (nearest-neighbour confusability): mean
  0.51 / 0.58 / 0.62 at N = 200/700/2000 — 117-141 analytic null-sd above
  the analytic floor. i.i.d. control codebook sits on the analytic curve
  (floor 0.0343 vs 0.0400 predicted), so the machinery is sound.
- BUT binding scrambles most of it: the substrate-level miss statistic
  (calibrate_null, actual unbind of never-written queries) is (0.0718,
  0.0165) at N=500 vs analytic (0.0390, 0.0041) — floor x1.8, sd x4.
  Displacement of the true floor from the analytic anchor: 7.1 sd.

Embedded gate vs the E2 synthetic ceiling (same code, same theta, EMBEDDED
null moments; encoder/embedded_vs_synthetic.csv):
- Ignorance AUC(u): k=10: 1.0000 vs 1.0000 | k=50: 0.9945 vs 1.0000 |
  k=100: 0.9002 vs 0.9998 | k=200: 0.6888 vs 0.9792.
- The collapse is NOT anomalous — it is the E2 capacity law fed with the
  MEASURED null moments: k_max drops 420 -> 123, paging 210 -> 62, k_sat
  344 -> 82. Observed AUC dies exactly where the law predicts. The law
  transfers; the constants shrink 3.4x.
- mu_hit(k) still tracks sqrt(2/(pi*k)) on embedded hits (slightly
  elevated: 0.156 vs 0.146 at k=30) but hit sd is ~1.7x the synthetic
  value — the EMBEDDED mode currently only measures the null side; a
  fully-measured mode (hit side too) is part of the fork discussion.
- *** C3 SPLIT EMBEDDED: AUC(d) = 0.8374 at the E2-spec load k_eff=70
  (synthetic ceiling 0.9988). STOP RULE FIRED (< 0.90). ***
- C3 vs load (diagnostic, seed 770): 0.949 (k_eff=30), 0.944 (50),
  0.827 (60), 0.829 (70), 0.724 (90). Within the embedded paging envelope
  (k_eff <= 62) the split clears 0.90 but sits ~0.05 below the ceiling.

Decision: E3 HALTED after Part 1 per the stage plan. Parts 2-4 (mouth,
write path, loop) not built. The stop-rule test xfails with the measured
number so a rerun can't silently pass. Design fork to decide (data above):
  (a) L2 top-2 ambiguity detection instead of L1 margin — sidesteps the
      margin's sensitivity to the widened null;
  (b) decorrelating projection (whiten embeddings before sign) — attacks
      the root cause (pairwise sd 9x analytic) and would recover envelope
      AND margin at once, but changes the encoder path;
  (c) accept the reduced envelope (page at ~62, C3 ~0.94) — no code
      change, materially weaker headline.
Prefetched for Part 2 whenever it unblocks: SmolLM3-Q4_K_M.gguf sha256
8334b850b7bd46238c16b0c550df2138f0889bf433809008cc17a8b05761863e
(ggml-org/SmolLM3-3B-GGUF), llama-cpp-python 0.3.34 CPU wheel (no GPU in
this WSL2 env — /dev/dri absent; CPU fallback is the primary path, logged
per the scope guard).

Surprise worth flagging: the projection preserves embedding correlation
almost perfectly (sign() does not decorrelate), yet MAP binding launders
most of it — two orders of magnitude of confusability (LOO max 0.58)
compress to a 1.8x floor elevation at the substrate level. The substrate
is doing real work; the encoder is the bottleneck, exactly as the
stage-ordering assumed.
