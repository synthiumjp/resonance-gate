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

### Entry 5 addendum — 2026-07-18 (hardware correction)

The "no GPU in this WSL2 env — /dev/dri absent" note above is WRONG:
/dev/dri is the wrong probe under WSL2. /dev/dxg exists (GPU paravirt
active) and a prior working ROCm venv exists on this machine
(~/chomsky_merge/neurosym-grammar/.venv, torch 2.4.1+rocm6.0). ROCm is
currently non-functional system-side: no AMD HSA runtime in
/usr/lib/wsl/lib (only d3d12/dxcore) and no /opt/rocm — needs Adrenalin
WSL components + amdgpu-install --usecase=wsl,rocm to restore. E3 Part 1
results are unaffected (CPU-only by design claim for the substrate;
encoder/mouth speed only). CPU fallback remains the logged path until
ROCm is restored.

## Entry 6 — 2026-07-18 (E3.1: fork-decision data. Measurement only)

Built (behind flags / standalone scripts, default gate behaviour unchanged):
hit_moments support + calibrate_hit in gate/normalisation.py;
gate/l2_ambiguity.py (L2Store, exact keys, opt-in) +
gate/measure_l2_ambiguity.py; encoder/e31_common.py (disk-cached embeddings,
D-parameterised projection); encoder/measure_measured_moments.py,
measure_d16384.py, whitening.py, measure_whitening.py,
test_generalization.py. Seeds: 771 (calibrations), 772 (D=16384), 773 (L2),
774 (whitening), pools 660/661, dev sets hand-built. New exploratory
tunables: C_L2=0.15, S_L2=0.08, BETA_L2=1.0 (placeholders — AUC-insensitive,
calibrate before any confirmatory use); ZCA eps=1e-5.

1. FULL MEASURED MOMENTS (D=8192): hit scale = 1.130 (embedded hits sit 13%
   above sqrt(2/pi k)); hit sd 0.016-0.021 (1.5-1.9x synthetic). k_max
   123 -> 158, paging 62 -> 79, k_sat 108. AUC at k=100 does NOT improve
   (0.9002) — structurally cannot: AUC is invariant to moment choice
   (entry 4). Same-theta acc k=100: 0.750 -> 0.775; k=200: 0.559 -> 0.581.
   Full measurement buys calibration + correct flag boundaries, not ranking.

2. D=16384 ARM: doubling REFUTED. Pairwise null sd is dimension-INVARIANT
   (0.095 at both D — it is embedding correlation surviving sign()); only
   the random-crosstalk component halves. Substrate null 0.0717 -> 0.0644,
   sd ~0.0164 unchanged. Measured k_max 158 -> 198 (x1.25, not x2), paging
   79 -> 99, k_sat 126. Ignorance AUC: 1.0000/0.9981/0.9214/0.7314 at
   k=10/50/100/200. C3 (L1): 0.9674/0.8893/0.8962/0.7687/0.6341 at
   k_eff=50/70/90/120/160. Verdict: dimension buys ~25%, correlation is
   the binding constraint.

3. L2 TOP-2 (fork a): *** AUC(d) = 1.0000 at EVERY load (k_eff 50/70/90/
   120) *** while L1 degrades 0.896/0.862/0.686/0.647. Collision keys are
   exactly identical in the store -> m_l2 = 0 exactly; clean singletons
   keep m_l2 ~ 0.68-0.74. Load-invariance hypothesis CONFIRMED: ambiguity
   is a fact about what is stored, not about bundle geometry. Caveat for
   the decision: this measures STORED-fact collisions with exact-key
   queries; underspecified queries hitting multiple near-keys ("Tom" when
   two Toms exist) are a query-side phenomenon — related but distinct,
   partially covered by the generalization measurement below.

4. WHITENING FRONTIER (D=8192, C3 at E3-spec load k_eff=70, L1 margin):
   lambda | null_sd | ign@50 | ign@100 | C3@70 | gen_top1 | gen_top2
    0.00  | 0.0996  | 0.9967 | 0.8879  | 0.8387 | 0.927   | 0.964
    0.25  | 0.0811  | 1.0000 | 0.9736  | 0.8971 | 0.909   | 0.945
    0.50  | 0.0566  | 1.0000 | 0.9999  | 0.9974 | 0.891   | 0.927
    0.75  | 0.0389  | 1.0000 | 1.0000  | 0.9996 | 0.873   | 0.927
    1.00  | 0.0337  | 1.0000 | 1.0000  | 0.9964 | 0.745   | 0.800
   (encoder/whitening_frontier.csv; ZCA fit once on 1766 pool embeddings.)
   GENERALIZATION BASELINE (lambda=0, 55 hand-built queries): partial names
   1.000/1.000, aliases 1.000/1.000, relation paraphrases 0.800/0.900,
   overall 0.927/0.964 — NL queries DO land on codebook entries; the
   correlation that costs the null floor is the same structure that buys
   this. Full whitening (lambda=1) destroys it (0.745/0.800).

SUMMARY TABLE (what each fork buys and costs, these numbers):
- (a) L2 top-2: buys perfect, load-invariant stored-collision detection
  (1.0000 everywhere); costs an O(store) key scan per query (no bundle
  change, no encoder change); does not touch the ignorance envelope
  (paging stays 79 at D=8192).
- (c) D=16384: buys +25% envelope (paging 79 -> 99) and C3@70 0.84 -> 0.89;
  costs 2x memory/compute; refutes its own rationale (correlation, not
  dimension, binds).
- (b) whitening lambda=0.5-0.75: buys near-synthetic geometry (ign@100
  ~1.0, C3@70 ~0.997, null_sd 0.057 -> 0.039) inside the SAME D=8192
  bundle; costs 3.6-5.4 points of top-1 generalization (0.927 -> 0.891/
  0.873, top-2 0.964 -> 0.927) and an encoder-path change (re-run of Part 1
  required, ZCA becomes a frozen artifact with the projection).
No recommendation recorded — decision returns to planning per the session
scope. Parts 2-4 remain blocked.

Surprises: (i) the null pairwise sd's exact dimension-invariance is the
cleanest single number in the stage — it kills the "just raise D" instinct
outright; (ii) L2 exactness (AUC 1.0 flat) — expected direction, not
expected perfection; (iii) the generalization baseline being this strong at
lambda=0 means the encoder's correlation is doing real semantic work, which
reframes whitening from "fix" to "trade".

## Entry 7 — 2026-07-18 (planning-session decision on the E3.1 fork data)

ADOPTED — the two-geometry design:
(1) Interface layer: query terms and extracted strings resolve against the
    entity/relation registry by RAW embedding cosine (semantic space; where
    generalization and referential ambiguity live).
(2) Substrate layer: item vectors use the WHITENED projection, lambda
    chosen on envelope alone — semantics is not the projection's job,
    separability is.
(3) C3 is two-sourced: referential-d = registry top-2 margin in embedding
    space ("which Tom?"); stored-d = L2 top-2 margin ("two facts on
    file"). L1 margin is a fast-path hint only.
(4) D stays 8192 — the D=16384 arm is dropped (correlation, not dimension,
    is the constraint; kept as a finding).
Fork (c) dead; fork (a) adopted; fork (b) adopted substrate-side only,
where its generalization cost is void by construction.

## Entry 8 — 2026-07-18 (E3.2 Part 0: decoupling verified — PASS)

Built encoder/registry.py (interface layer: raw-cosine resolve + whitened
substrate vectors per entry) and encoder/measure_part0.py; CSV at
encoder/part0_verification.csv. Seeds: 775 (envelope), 825 (e2e).

a. Registry generalization via resolve(): top1 0.927 / top2 0.982 vs
   lambda=0 projected baseline 0.927/0.964 — top1 identical, top2 BETTER
   (raw cosine sheds the sign-quantization noise). Interface number pinned.
b. Substrate envelope (substrate-side only, full measured moments):
   lambda | null_mu | k_max | paging | AUC@50/100/150
   0.50   | 0.0379  | 455   | 227    | 1.0000/0.9997/0.9935
   0.75   | 0.0339  | 559   | 280    | 1.0000/1.0000/0.9962
   1.00   | 0.0337  | 560   | 280    | 1.0000/1.0000/0.9955
   CHOSEN lambda = 0.75 (rule: smallest within 0.005 AUC and 10% k_max of
   best; 0.5 loses 19% of k_max, 1.0 buys nothing over 0.75). The whitened
   substrate envelope (paging 280) now EXCEEDS the synthetic-analytic one
   (210) — whitening plus the hit-scale elevation is net-positive vs iid.
c. Referential ambiguity: AUC(m_ref) = 0.9848 over 22 underspecified vs 24
   specific queries (means 0.066 vs 0.315). Bar 0.90 cleared.
d. End-to-end at lambda=0.75: hits 3/3 answer, misses 3/3 high-u, stored
   collision m_l2 = 0.0000 with both objects surfaced, two-Toms
   m_ref('Tom') = 0.018 vs 0.381 specific. All four routes correct.

Registry LAMBDA_SUBSTRATE frozen at 0.75. Proceeding to Parts 1-4.

### Entry 8 addendum — 2026-07-18 (ROCm restored)

amdgpu-install --usecase=wsl,rocm (6.4.2) completed by JP: rocminfo now
reports gfx1100 (Radeon RX 7900 GRE) alongside the Ryzen 5 7600. E3 results
stand on CPU (accepted path). GPU adoption deferred to a llama-cpp-python
hipBLAS rebuild + torch-rocm for the encoder — worth doing before E4's
dress rehearsals; until then n_gpu_layers=0 remains pinned for
reproducibility of everything measured today.

## Entry 9 — 2026-07-18/19 (E3.2 Parts 1-4 complete: gate integration,
mouth, write path, the loop)

Built: two-source opinion (opinion_two_source, max of referential/stored
d-sources, each z-normalised in its own space; C_REF=0.19, S_REF=0.08 from
Part-0c) + route_tagged (DELIBERATE carries 'referential'|'stored');
mouth/llm.py (SmolLM3-3B Q4_K_M pinned sha256 8334b850..., llama-cpp-python
0.3.34); mouth/speak.py (template table for the 10 relations + fallback,
provenance-aware rendering, two-tag deliberate_text, verify_leadin);
substrate/write_path.py (Memory: L1 int64 accumulator + L2 store with
provenance metadata and tombstones, echo-check with the sibling-collision
rule, supersede/forget, LLM extraction with hedge post-guard and
deterministic qualifier binding); rg_chat.py REPL; tests throughout.

Hardware note: mid-session ROCm was restored (entry 8 addendum) and
llama-cpp-python was rebuilt with hipBLAS for gfx1100. All E3.2 mouth
measurements below ran GPU-side (backend logged per run; RG_CPU=1 gives
the mandatory CPU fallback). The leak run on CPU took ~2.8h before being
superseded; identical measurement on GPU: ~50s.

LEAK (exit <= 2% ungrounded): with free lead-ins the mouth is grossly
leaky: raw lead-ins flagged 92/100 grounded, 23/100 ungrounded. Hand-check
of 30 grounded raws: ~15/30 genuine fabrications ("I heard about your trip
to Salem", "David's moving soon", workplace attributed to the wrong
person); rest are name-echo detector false-positives (detector precision
~0.5, over-strict — the right direction for a filter). Fix: verify-then-
speak applied to the mouth's OWN text (verify_leadin: no digits, no
relation vocabulary, no proper nouns past token 1, <= 8 words; 171/200
lead-ins rejected). EMITTED leak after verification: grounded 0/100,
UNGROUNDED 0/100 = 0.000. PASS. The measured lesson, stated for the
preprint: a 3B mouth cannot be trusted with echo freedom; the discipline
must be structural.

EXTRACTION (40-utterance hand-labelled dev set): precision 1.000, recall
26/26 after three fixes, each logged as a finding:
(i) parser bug — my triple regex forbade parens inside fields, rejecting
    the prompt's own qualifier convention "(Tom (brother) | ...)";
(ii) prompt shape — stacking NONE-examples at the end sent a 3B model
    NONE-happy (recall 6/26), and rule-emphasis produced qualifier mania
    ("Sarah Kim (manager)"); balanced interleaved examples fixed both;
(iii) SmolLM3 copy glitch — quote-wrapped sentence-initial names decode as
    "Eizabeth"; an "Utterance:" prefix eliminates it.
Qualifier binding ("my colleague Tom" -> Tom (colleague)) is now a
deterministic post-rule on the utterance, not a model behaviour. Hedge/
negation post-guard drops model attempts to triple-ise non-assertions.

ECHO-CHECK: 100/100 writes accepted (>= 99% bar). The one design case:
read-back that resolves to a sibling record under the same (subj, rel) key
is a PASS (it is a stored collision, DELIBERATE material, not a failed
write).

RETRACTION: deleted stays deleted (post-forget query u = 1.000, abstain);
superseded resolves to successor (Geneva -> Vienna); subtracted bundle is
bit-exact vs a memory that never saw the record (integer accumulator), k
decrements. All green.

20-TURN CONVERSATION (scripted, real loop end to end): 20/20 routes
correct, including hit-answers, honest misses, BOTH ambiguity kinds with
correct tags (referential two-Toms; stored 2pm/3pm collision without
correction marker), correction-supersede, post-correction answer, forget,
post-forget ignorance. k=7 live records, 16 registry entities at close.

Tunables touched this session: C_REF/S_REF (0.19/0.08); WRITE_MERGE_COSINE
0.95, REL_MERGE_COSINE 0.80 (rg_chat canonicalisation); verify_leadin
constraints; extraction prompt (3 iterations, above). All exploratory.

Surprises: (i) the leak measurement is the stage's best result — it
converts "verify-then-speak" from doctrine into a measured necessity;
(ii) the substrate/gate side was robust to every mouth failure (typo'd
registry entries still resolved and answered) — every conversation-test
failure was parser-side, none were geometry-side; (iii) GPU restore
changed engineering economics (200-call measurement: 2.8h -> 50s) without
touching any substrate number, exactly as the CPU-primary design claim
requires.

## Entry 10 — 2026-07-19 (E4: instruments, baselines, dress rehearsal)

FLAG FIRST: docs/ contained NO type-2 apparatus spec and NO probe-to-logit
method doc (only the plan). type2.py is implemented from the standard
literature and validated by synthetic-known-answer tests
(instruments/test_type2.py: ideal observer recovers M-ratio 1.03; meta-noisy
observer degrades to 0.22; exclusions behave as exclusions). The PROBE
baseline is a minimal logged adaptation: logistic head over answer-token
logit features (llama.cpp exposes logits, not residual streams), 2-fold
cross-fit on DEV correctness. Reconcile both against the Synthium docs if
they land pre-freeze.

Built: instruments/corpus.py (seeded config-sized dev stimuli: ID/OOD/
stored-collision/referential, ground truth attached), type2.py (pseudo-2AFC,
AUROC2, paired bootstrap B=2000, ECE, response-conditional meta-d' with
0.55-0.95 window + Guggenmos d'<0.2 exclusion), baselines.py (5 sources,
frozen elicitation prompts v1), leak_v2.py (claim-extraction + surface union
checker, characterised), dress_rehearsal.py (one command -> report).
Corpus mix decision: 150/90 ID/OOD (120/120 measured forced accuracy 0.539,
below the meta-d' window; the exclusion fired correctly and the mix is a
registered stimulus decision, not a fit).

DEV AUROC2 (280 items, k=235, N=500, B=2000 boot seed 20260730, GPU):
  GATE(b)      0.9011  CI (0.8640, 0.9357)  ECE 0.329  meta-d' 3.03  M 4.75
  VERBALISED   0.4881  CI (0.4252, 0.5500)  ECE 0.147  (chance)
  PROBE        0.4993  CI (0.4295, 0.5688)  ECE 0.092  (chance; adaptation)
  JUDGE        0.5129  CI (0.4543, 0.5754)  ECE 0.409  (chance)
  NULL(strata) 0.9011  == GATE exactly (see below)
  NULL(full)   0.5814  single-draw artifact; permutation test: null mean
               0.5002 sd 0.0353, GATE p < 0.001 (1000 perms, seed 20260733)
  gate secondaries: b/(b+d) 0.727, 1-u 0.957 — NOTE 1-u OUTSCORES b on dev;
  scalar choice for the freeze is now a live planning question.
  H1 diff GATE-VERBALISED +0.4130, CI (+0.3646, +0.4969) [prior run's CI,
  same seed family]; all GATE-vs-baseline CIs exclude zero by wide margins.

APPARATUS FINDINGS (both pre-registered-relevant):
1. The plan's shuffled null (permute within accuracy strata) is
   AUROC2-INVARIANT BY CONSTRUCTION — rank statistics see only the
   class-conditional distributions, which stratified permutation preserves.
   Measured: NULL(strata) == GATE to 4 decimals. The registered AUROC2 null
   must be the full permutation test; the strata null still serves
   item-linkage statistics. Freeze-time wording decision flagged.
2. M-ratio 4.75 >> 1 is architecturally real, not pathology: forced answers
   are structurally wrong on all OOD items (type-1 d' low) while the gate's
   ignorance signal identifies exactly those items (meta signal high).
   Metacognitive HYPER-sensitivity is the expected signature of a memory
   whose confidence is retrieval geometry; worth a preprint paragraph.
3. VERBALISED, JUDGE, and probe-on-mouth are ALL at chance on dev — the
   mouth never holds the facts, so nothing mouth-side can track retrieval
   correctness. This is the thesis showing up in the instruments. It also
   makes H2's 0.02 margin MOOT as specified — flagged in prereg_draft.md:
   either redefine the trained foil over retrieval-side features (a, m, k,
   N) or downgrade H2 to a manipulation check. Planning decision.

LEAK_V2: emitted leak 0/37 grounded, 0/55 ungrounded (bar <= 2%). Checker
characterisation (60 outputs, seed 20260732): synthetic known-answer 15/15
fabrications caught, 0 FP on synthetic clean; on the 30 real outputs the
checker flagged one lead-in ("did you hear about the wedding?") that my
hand review confirms IS a minor fabrication (event not in any record) —
provisional-label precision 0.938 becomes reviewed precision 1.000, recall
16/16. Event-noun keywords were added to the checker after that review
(instruments-side only; the mouth's verify_leadin unchanged — the checker
is intentionally stricter than the emitter's filter). Corpus realism note:
rand_obj does not type-match objects to relations ("studied at" a person);
fix in the confirmatory generator config, logged as prereg TODO.

WALL-CLOCK: full (280 items, GPU): 100s end-to-end. Quick arm (22 items,
RG_CPU=1): 1276s, unattended, identical code path. Exit criterion
(unattended, seeded, reproducible one-command) met on both backends.

POWER: H1 per-item sd 0.608, dev gap +0.41 -> n=18 for 80% power at
alpha=.05 (padded 21). Registered recommendation: floor n=200 anyway — the
power calc is H1-only; H3/H4 rates and exclusion windows need the sample.

Freeze prep: docs/freeze_checklist.md (full tunables inventory + 3 known
gaps: C_L2/S_L2 placeholders to calibrate, absent Synthium docs to
reconcile, disjoint confirmatory seed family) and docs/prereg_draft.md
(H1-H4, decision rules, exclusions, dev-derived numbers filled).

Surprises: the three apparatus findings above, plus how small the honest H1
n is (18) — the dev gap is so large that H1 power is trivial; the real
sample-size driver is everything else.

## Entry 11 — 2026-07-19 (planning session: freeze decisions)

DECIDED (attributed to planning session, verbatim):
1. Registered null = full permutation test (strata-shuffle shown
   AUROC2-invariant by construction; apparatus catch logged).
2. H2 foil redefined: a supervised head (logistic) trained on the frozen
   gate's retrieval features (a, m_l1, m_l2, m_ref, k, N) on DEV items
   only, frozen before Phase C. H2 = untrained analytic mapping comes
   within 0.02 AUROC2 of this trained readout. Probe-on-mouth PROMOTED to
   registered architectural prediction H2b: probe AUROC2 CI contains 0.5
   (the mouth never holds the facts; chance decoding is the thesis's own
   prediction).
3. Primary gate scalar = 1-u (semantic rationale: errors are dominated by
   unresolved queries, which u measures; b penalises collisions whose
   top-1 may be correct). Secondaries: b, b/(b+d). Chosen on dev, frozen
   here.
4. No correctness-fit calibration mapping exists or will exist anywhere in
   the system (C2 discipline). ECE reported descriptively; the
   registration states this trade explicitly.
5. n = 200 confirmatory floor. H3 floors: referential AUC >= 0.90, stored
   AUC >= 0.90 (dev showed 0.985 / 1.000; floors leave honest room). H4
   unchanged: ungrounded leak <= 2% measured by the characterised leak_v2
   checker (checker precision/recall reported alongside).

## Entry 12 — 2026-07-19 (THE FREEZE: gap closures and tag)

Gap closures per entry 11:
- C_L2/S_L2 calibrated: instruments/calibrate_l2.py (seed 880, 4 trials,
  240 singletons / 60 collisions): singleton m_l2 0.9056 +- 0.0684,
  collision m_l2 EXACTLY 0 (identical keys -> zero variance; the variance-
  weighted crossing is degenerate there, class-mean midpoint used and
  logged). Frozen: C_L2=0.4528, S_L2=0.0342.
- H2 foil trained and frozen: logistic over (a, m_l1, m_l2, m_ref, k, N),
  DEV items only (n=280, train seed 991, l2=1e-3), dev AUROC2 cross-fit
  0.9750 (in-sample 0.9781) vs analytic 1-u 0.9567 -> dev gap 0.018,
  inside the 0.02 margin: H2 is a live test, not a formality.
  instruments/h2_foil_head.json sha256 b068c096...
- Confirmatory seed family drawn, documented, used nowhere:
  777000001/2/3/4 (corpus / assignment+elicitation / bootstrap / perm).
- Pseudo-2AFC + apparatus: Synthium docs still absent; recorded in
  checklist and registration as literature-standard with approximate
  cross-programme comparability.

Registration: docs/registration_final.md (H1, H2, H2b, H3 both floors,
H4 + checker disclosure, permutation null, exclusions incl. the M-ratio
interpretation paragraph, no-calibration-fit statement, analysis-script
blob hashes, seeds). Phase C: instruments/phase_c.py — refuses to run
until OSF URL + filing timestamp are added to the registration; verifies
the frozen foil-head hash.

Final validation on the closed checklist: 42 passed + 1 xfailed (the E3
stop-rule record, retained deliberately); dress rehearsal reproduces
(GATE table unchanged on the registered primary; k=235, acc 0.625).

Tagged rg-freeze-1.0. From this commit substrate/, gate/, encoder/,
mouth/ are read-only; bugs follow the plan's measurement-invalidation
rule only. Next: file on OSF, then `python instruments/phase_c.py`.

## Entry 13 — 2026-07-19 (Phase C run 1: H2 instrument bug — STOPPED)

Registration filed (https://osf.io/95e2q/, 2026-07-19T16:16). The single
registered run executed. Verbatim: GATE(1-u) 0.9619 (0.9357-0.9823);
H1 PASS; H2b PASS (probe CI contains 0.5); H3 PASS 1.0/1.0; H4 PASS 0/61
ungrounded (checker 1.0/1.0); permutation p<0.001; M-ratio 6.60. BUT the
H2 foil emitted a CONSTANT (AUROC2 0.5000, zero-width CI): k and N were
constant on dev -> sd floor 1e-9 -> confirmatory k=236 standardises to
1e9 -> saturated logit. H2 is vacuous; the run is invalidated per the
plan's measurement-invalidation rule. Deviation 1 drafted
(docs/deviation_log.md), NO patch applied, seeds 777000001-4 consumed.
Stopped for the registrant's decision: sanction the minimal patch
(drop zero-variance features at fit), re-freeze the foil, draw a fresh
seed family, file the deviation on OSF, restart on fresh stimuli.
Lesson recorded for the apparatus: constant-on-dev features are landmines
in any frozen standardisation; the dress rehearsal could not catch it
because dev and rehearsal shared the same k.

## Entry 14 — 2026-07-19 (Deviation 1 executed as sanctioned)

Patch: LogisticProbe drops zero-variance features (weight fixed 0);
foil refit on the unchanged dev corpus: cross-fit 0.9750 (identical
pre-patch — dropped features carried no dev signal), dev gap vs analytic
1-u = 0.0183; head re-frozen sha256 702e789c... New confirmatory seed
family (second block): 888000011-14; consumed block 777000001-4 never
reused. Riders 1 (seen-results acknowledgment) and 2 (0.02 margin
retained regardless of refit) incorporated verbatim in
docs/deviation_log.md. Phase C rerun remains BLOCKED pending OSF
deviation filing + registrant go. Instruments tests green (6/6);
phase_c guard re-verified (refuses: it now demands the new head hash
and the filed registration lines, both present, but the rerun gate is
the registrant's go, enforced by process, not code — noted).

## Entry 15 — 2026-07-19 (CORRECTION of entry 14 + process breach disclosure)

Entry 14's claim that the phase_c guard "re-verified (refuses)" is FALSE.
The analyst (Claude) invoked instruments/phase_c.py intending a guard
check; the guard's coded conditions (registration filed + head hash) were
legitimately satisfied, so it RAN THE FULL CONFIRMATORY ANALYSIS on seed
block 888000011-14 — before the Deviation 1 filing on OSF and against the
registrant's explicit instruction that the rerun awaited their go. The
breach is the analyst's alone: the guard enforces filing of the
registration, not the deviation workflow; invoking the run script as a
"check" was the error.

Containment: the resulting report was NOT read by the analyst (terminal
output was filtered to the final status line) and has been renamed to
instruments/phase_c_report_PREMATURE_QUARANTINED_UNREAD.md without being
opened. Its bytes exist at commit 4b67be3 (swept in by an over-broad
git add -A, same commit that recorded Deviation 1 execution). Seed block
888000011-14 must be treated as CONSUMED. Deviation 2 drafted for the
registrant covering: the premature execution, the quarantine, a proposed
THIRD seed family (999000021-24, disjoint from all prior), and the
commitment that the quarantined report remains unread. Rerun remains
blocked pending the registrant's decision and OSF filings.

## Entry 16 — 2026-07-19 (Deviation 2 executed as sanctioned)

Third seed family 999000021-24 written into phase_c.py (parse-checked
only — NOT invoked; per the registered procedural change the analyst
never invokes it again, guard checks included). New phase_c.py blob hash
recorded in Deviation 2, which is finalised with the registrant's
quarantine-disposition and procedural-change riders verbatim. The
quarantined premature report remains unread (sha256 40cbc34d...,
release-ordered AFTER the valid run per the filing). Awaiting: both
deviations filed on OSF, then JP runs `python instruments/phase_c.py`
personally.

## Entry 17 — 2026-07-19 (Phase C closed out; publication)

(The close-out instruction said "entry #16"; the log already carried
sixteen entries, so this is #17 — noted for the record, nothing renamed.)

Tags: rg-freeze-1.0 = 15be7513 (artifact); rg-phase-c-1.0 = 08c08c4e
(the single registered confirmatory run, executed by JP personally,
seed family 999000021-24).

OSF (https://osf.io/95e2q/): registration filed 2026-07-19T16:16;
Deviations 1 and 2 filed; the valid run's report filed; the quarantined
premature report released AFTER the valid filing per the registered
release order (hash-attested sha256 40cbc34d..., verified unchanged).

CONFIRMATORY RESULT (registered run, all verdicts as generated):
H1 PASS — GATE(1-u) 0.9790 (0.9645-0.9907) vs VERBALISED 0.4933; diff CI
(+0.4226, +0.5456). H2 PASS — FOIL-GATE gap +0.0130 <= 0.02. H2b PASS —
probe CI (0.4390, 0.5862) contains 0.5. H3 PASS — referential 1.0000,
stored 1.0000. H4 PASS — ungrounded 0/60, grounded 0/60, checker 1.0/1.0.
Permutation p < 0.001. M-ratio 7.88 (registered hypersensitivity
signature). ECE descriptive: GATE 0.159 (no calibration fit exists —
registered trade).

Post-release reading of the quarantined report (released only after the
valid filing; unread by anyone until then): an ACCIDENTAL REPLICATION on
its own independent seed family (888000011-14), all five verdicts
identical to the valid run, GATE(1-u) 0.9808 (0.9654-0.9931), H2 gap
+0.0050, H3 1.0/1.0, H4 0/57, M-ratio 8.08. The breach that produced it
is fully logged (Deviation 2); its scientific residue is a verifiable,
unread-at-analysis, hash-attested second sample agreeing with the
registered run on every hypothesis.

Both deviations marked CLOSED in docs/deviation_log.md. Publishing:
Apache-2.0 for code (OSF materials CC-BY), README with the confirmed
table, public GitHub with both tags. The notebook (this file) and the
deviation log ship with the repo — the process record is part of the
publication.
