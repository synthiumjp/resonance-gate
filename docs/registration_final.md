# RG confirmatory study — registration (final; file on OSF, then fill the two lines below)

OSF URL: PENDING
Filed: PENDING

Artifact: tag rg-freeze-1.0 = commit 15be7513b32af89abe519a7b48e588565fee12d2 (tag object 7210edc71adbbd3d71f8a44908e6217f3c1ebdc4).
Tunables inventory: docs/freeze_checklist.md (frozen with the tag).
Exploratory record: notebook.md entries 1-12 (append-only lab log).

## System under test
The Resonance Gate (RG): a VSA/MAP memory substrate (D=8192, whitened
projection lambda=0.75 substrate-side) in which retrieval and confidence
are the same operation; two-geometry interface (raw-cosine registry);
two-source ambiguity (referential + stored); SmolLM3-3B mouth under
template-forward verify-then-speak. No confidence-specific training exists
anywhere in the gate path, and NO correctness-fit calibration mapping
exists or will exist in the system (C2 discipline): ECE is reported
descriptively and this trade is accepted in advance.

## Hypotheses and decision rules (one run, registered seeds, two-sided alpha=.05)

Primary gate scalar (frozen, chosen on dev): 1-u. Secondaries (reported,
never substituted): b, b/(b+d).

- H1 (endogeneity, primary): AUROC2(GATE 1-u) > AUROC2(VERBALISED);
  paired-bootstrap (B=2000, seed 777000003) 95% CI of the difference
  excludes zero. Dev evidence: gap +0.41 [E4]. Falsified -> published as
  the negative it is.
- H2 (parity with a trained readout): AUROC2(FOIL) - AUROC2(GATE 1-u)
  <= 0.02, where FOIL is the frozen logistic head over the gate's own
  retrieval features (a, m_l1, m_l2, m_ref, k, N), trained on DEV only
  (instruments/h2_foil_head.json, sha256 b068c096dd6cf9f8...; dev
  cross-fit AUROC2 0.9750 vs analytic 0.9567, dev gap 0.018).
- H2b (architectural prediction): AUROC2 of the probe-on-mouth baseline
  has a 95% CI containing 0.5. The mouth never holds the facts; chance
  decoding is the thesis's own prediction, promoted from baseline to
  registered claim.
- H3 (ignorance/ambiguity separation): referential-d AUC (referential
  probes vs clean correct ID) >= 0.90 AND stored-d AUC (planted
  collisions vs clean correct ID) >= 0.90. Dev: 0.985 / 1.000.
- H4 (gate discipline): ungrounded emitted leak <= 2%, measured by the
  characterised leak_v2 checker; checker precision AND recall on its
  60-output labelled sample reported alongside the rate.

Null model: FULL permutation test (1000 permutations, seed 777000004) of
the primary scalar against correctness. (The plan's strata-shuffled null
is AUROC2-invariant by construction — apparatus finding, entry 10 — and is
therefore not the registered null for rank statistics.)

## Exclusions
- meta-d'/M-ratio: computed only if forced-answer accuracy is in
  [0.55, 0.95] and d' >= 0.2 (Guggenmos); otherwise excluded and reported
  as excluded, never force-fit. AUROC2/ECE/leak have no exclusions.
- Echo-check-rejected writes are logged and excluded from ID sampling
  (never stored).
- Interpretation note (registered in advance): M-ratio > 1 is the
  PREDICTED signature, not an anomaly — the type-2 signal (retrieval
  geometry) has access to resolution failure that the forced type-1
  answer lacks, so metacognitive hypersensitivity is expected for a
  memory whose confidence is its retrieval geometry.

## Stimuli and n
- Confirmatory corpus: instruments/corpus.py, CorpusConfig(seed=777000001,
  n_entities=500, n_facts=160, n_id=150, n_ood=90, n_coll=20, n_ref=20)
  -> 280 items (>= registered floor n=200). Seed family disjoint from every
  dev seed (dev family documented in entries 5-10).
- Registered seeds: corpus 777000001, item assignment/elicitation
  777000002, bootstrap 777000003, permutation 777000004. Used nowhere
  before Phase C.

## Analysis
- One command: `python instruments/phase_c.py` (refuses to run until the
  OSF URL and filing timestamp are entered above; verifies the frozen
  foil-head hash before running).
- Script blob hashes at the freeze tag (git hash-object):
  - instruments/phase_c.py: d151fac35329bf1b557daf9a83bc90250695534c
  - instruments/corpus.py: 7b9c0e8ea4da4339fefed585302ed9de5d6bc35b
  - instruments/type2.py: 8a0d6b42f14267588343ef8a750c31491ab64fe1
  - instruments/baselines.py: 47e85d8cae98670ffbcbcde8969c6e9faa8cfaac
  - instruments/leak_v2.py: bbfe976522aab13ea670f9551753343297ab18f3
  - instruments/h2_foil.py: 344653b4060b8db5abe89c99ca3b08ca8d1bb65a
  - instruments/calibrate_l2.py: 5eb45185414444c33abc0e273c5b409cb0ee23e0
  - instruments/dress_rehearsal.py: 3064adb4b7cf823eadf599ef2e1c3ef7611c0fac
- Backend: GPU (hipBLAS gfx1100); RG_CPU=1 is the registered fallback and
  changes no substrate/gate number (E3.2 evidence, entry 9).

## Known adaptations (registered deviations)
- Type-2 apparatus and pseudo-2AFC: literature-standard implementations
  validated by synthetic-known-answer tests (instruments/test_type2.py);
  the Synthium apparatus doc was absent from docs/ at freeze —
  cross-programme comparability is approximate.
- Probe-on-mouth features are answer-token logits (llama.cpp exposes
  logits, not residual streams).
- Deviation log: any departure from this document is dated and logged in
  the deviation log published with the OSF filing; results are reported
  whichever way they fall.
