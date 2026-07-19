# The Resonance Gate

A research build of a memory substrate in which **retrieval and confidence
are the same operation**. Facts live in a vector-symbolic (MAP/VSA) bundle;
the geometry of cleanup — resolution `a`, margins in three spaces — is
normalised by closed-form capacity law into a (belief, disbelief,
uncertainty) opinion that routes every answer: ANSWER, "which one do you
mean?" (referential), "I have two facts on file" (stored), or an honest
"I don't know". A frozen 3B LLM phrases gate-cleared content under
verify-then-speak; it is never a source of facts — a claim the study
design itself tests. No confidence-specific training and no
correctness-fit calibration exist anywhere in the system.

## Confirmed results (pre-registered, single run on the frozen artifact)

Registration: [OSF 95e2q](https://osf.io/95e2q/) (filed before the run;
deviation log included in full). Artifact: tag `rg-freeze-1.0`. Run: tag
`rg-phase-c-1.0`, executed by the registrant, seed family registered in
advance. n=280 items (ID / OOD / stored-collision / referential).

| hypothesis | registered rule | result |
|---|---|---|
| H1 endogeneity | gate (1-u) beats verbalised confidence; paired-bootstrap CI excludes 0 | **PASS** — AUROC2 0.9790 vs 0.4933; diff CI (+0.4226, +0.5456) |
| H2 trained-readout parity | supervised head over the gate's own features beats it by <= 0.02 | **PASS** — gap +0.0130 |
| H2b architectural prediction | probing the mouth's logits decodes correctness at chance (CI contains 0.5) | **PASS** — 0.5120 (0.4390, 0.5862) |
| H3 ambiguity separation | referential and stored ambiguity AUC >= 0.90 | **PASS** — 1.0000 / 1.0000 |
| H4 gate discipline | ungrounded leak <= 2% (characterised checker) | **PASS** — 0/60; checker precision/recall 1.0/1.0 |

Permutation null p < 0.001. Meta-d′/d′ = 7.9 — metacognitive
hypersensitivity, registered in advance as the predicted signature (the
type-2 signal has access to resolution failure the forced type-1 answer
lacks). An accidental second run on an independent seed family — produced
by a logged process breach, hash-attested and unread until after the
registered filing (Deviation 2) — replicates every verdict
(`instruments/phase_c_report_PREMATURE_QUARANTINED_UNREAD.md`).

## Reproduce

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev,encoder,mouth]"
.venv/bin/python -m pytest -s              # full suite (42 tests + 1 xfail kept as history)
.venv/bin/python substrate/capacity_sweep.py --seed 42     # E1 capacity curves
.venv/bin/python instruments/dress_rehearsal.py --seed 20260719   # E4 dev pipeline
```

The mouth needs `mouth/models/SmolLM3-Q4_K_M.gguf` (third-party, never
committed): `ggml-org/SmolLM3-3B-GGUF`, sha256 pinned in
`docs/freeze_checklist.md`. GPU (ROCm/hipBLAS) optional; `RG_CPU=1` is the
registered CPU fallback. `rg_chat.py` is a minimal REPL over the full loop.

`instruments/phase_c.py` is the registered confirmatory analysis: it is
guarded (refuses without the filed registration) and its seed family is
**consumed** — running it again produces a post-hoc number, not the
registered result, which lives at tag `rg-phase-c-1.0`.

Two binary artifacts are committed deliberately (`encoder/.emb_cache.npz`,
`encoder/zca_384.npz`): embeddings and the ZCA fit are BLAS-dependent, and
these bytes are the ones the registered runs consumed.

## Repo map

- `substrate/` — MAP algebra, capacity sweep, write path (O(1) append,
  echo-check, supersede/tombstone). `gate/` — load-normalised (b,d,u)
  opinion, two-source ambiguity, controller. `encoder/` — MiniLM →
  whitened seeded projection; raw-cosine registry (two-geometry design).
  `mouth/` — frozen SmolLM3-3B, template-forward verify-then-speak.
  All four frozen at `rg-freeze-1.0`.
- `instruments/` — type-2 apparatus (synthetic-known-answer validated),
  five confidence baselines, characterised leak checker, dress rehearsal,
  Phase C runner.
- `notebook.md` — the append-only lab log, entries 1–17, including every
  mistake. `docs/deviation_log.md` — both deviations, closed. The process
  record is part of the publication.
- `docs/` — project plan, freeze checklist (every tunable + provenance),
  registration.

## Honest limitations

- **ECE is reported, not optimised**: the gate's confidence is
  discriminative (AUROC2 0.979) but not calibrated as a probability
  (ECE 0.159), because fitting a calibration map to correctness is
  categorically excluded by design. That trade is registered.
- **Template fluency**: gate-governed answers are slot-filled templates
  with (verified) connective text; free generation measured 92%/23%
  fabrication-or-echo rates from a 3B mouth and is disabled on principle.
- **Synthetic corpus**: entities/relations are generated families
  (confusables included) with type-unmatched objects in places; no
  real-world knowledge, temporal reasoning, or multi-hop queries.
- Encoder correlation, not dimension, bounds capacity (measured; the
  D=16384 arm is kept as a negative result in the notebook).

## License

Code: Apache-2.0 (see LICENSE). OSF materials: CC-BY. Model weights are
third-party and referenced by pinned hash only.
