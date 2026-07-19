# The Resonance Gate

A research build of a memory substrate for which — in this class of
vector-symbolic (MAP/VSA) substrate — retrieval and confidence are the
same measurement: the geometry of cleanup (resolution `a`, margins in
three spaces), normalised by a closed-form capacity law, yields a
(belief, disbelief, uncertainty) opinion that routes every answer:
ANSWER, "which one do you mean?" (referential), "I have two facts on
file" (stored), or an honest "I don't know". The architecture treats the
substrate as authoritative; a frozen 3B LLM is constrained to verbalising
gate-approved content under template-forward verify-then-speak. No
confidence-specific training and no correctness-fit calibration exist
anywhere in the system.

**What this study shows** (pre-registered, single run on the frozen
artifact, then adversarially audited): on a synthetic exact-string
corpus, an untrained closed-form mapping of retrieval geometry carries
essentially all the correctness information available in that geometry —
it comes within 0.013 AUROC2 of a supervised readout trained on the same
features (registered margin 0.02), and a stronger gradient-boosted audit
foil does no better (**H2 — the headline result**). Confidence-bearing
routing — ignorance versus two typed ambiguity signals — is structural,
not trained. The same run separates written from unwritten keys nearly as
well as an explicit store-membership oracle (0.979 vs 0.941) and detects
same-key stored duplicates and same-name referential collisions perfectly
*as constructed*. Claims beyond this regime — error ranking among
answered items (n=12 errors here), near-duplicate ambiguity, paraphrased
queries, free-text leak safety — are not established by this study.

## Registered results (single run on the frozen artifact)

Registration: [OSF 95e2q](https://osf.io/95e2q/) (filed before the run;
deviation log included in full). Artifact: tag `rg-freeze-1.0`. Run: tag
`rg-phase-c-1.0`, executed by the registrant, seed family registered in
advance. n=280 items (ID / OOD / stored-collision / referential). The
registered letter of every decision rule holds; the post-audit column
records what each number does and does not establish.

| hypothesis | registered rule | result | post-audit status |
|---|---|---|---|
| H1 endogeneity | gate (1-u) beats verbalised confidence; paired-bootstrap CI excludes 0 | **PASS** — AUROC2 0.9790 (either-object scoring per registration; strict scoring 0.830, audit A1/A4) vs 0.4933; diff CI (+0.4226, +0.5456) | baseline architecturally unloseable — demonstrates the design, not a competition (audit A2) |
| H2 trained-readout parity | supervised head over the gate's own features beats it by <= 0.02 | **PASS** — gap +0.0130 | survived adversarial audit, including a stronger (gradient-boosted) foil — see audit/AUDIT_REPORT.md A6 |
| H2b architectural prediction | probing the mouth's logits decodes correctness at chance (CI contains 0.5) | **PASS** — 0.5120 (0.4390, 0.5862) | unfalsifiable as operationalised (audit A6); retained as design documentation, not evidence |
| H3 ambiguity separation | referential and stored ambiguity AUC >= 0.90 | **PASS** — 1.0000 / 1.0000 | stored-d: byte-identical key construction; near-synonym collisions not detected (audit A4) |
| H4 gate discipline | ungrounded leak <= 2% (characterised checker) | **PASS** — 0/60; checker precision/recall 1.0/1.0 | checker and emitter share vocabulary; negation/implication/temporal assertions untested (audit A5) |

## Adversarial audit (post-publication, pre-preprint)

Before any preprint, the project ran a hostile audit of the confirmatory
result ([audit/AUDIT_REPORT.md](audit/AUDIT_REPORT.md), commit 036dc5a):
it found that three of the five headline numbers (H1, H3 stored-d, H4)
are substantially guaranteed by evaluation design rather than earned by
the mechanism, and that a zero-parameter exact-key store-membership
oracle attains 0.941 of the 0.979 headline. Every registered number
reproduced bit-exactly under an independent reimplementation, the frozen
tree and all attested hashes verified clean, and H2 survived adversarial
attack including a stronger foil. The framing in this README reflects
those corrections (Deviation 3 in docs/deviation_log.md); no registered
number changed.

Permutation null p < 0.001. Meta-d′/d′ = 7.9 — registered in advance as
the predicted signature; the audit shows it is largely arithmetic of the
OOD-heavy design (the type-2 signal holds store-membership information
the forced type-1 answer is denied — audit A1). An accidental second run
on an independent seed family — produced by a logged process breach,
hash-attested and unread until after the registered filing (Deviation 2)
— replicates every verdict
(`instruments/phase_c_report_PREMATURE_QUARANTINED_UNREAD.md`).

## Reproduce

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev,encoder,mouth]"
.venv/bin/python -m pytest -s              # full suite (42 tests + 1 xfail kept as history)
.venv/bin/python substrate/capacity_sweep.py --seed 42     # E1 capacity curves
.venv/bin/python instruments/dress_rehearsal.py --seed 20260719   # E4 dev pipeline
```

**Reproducibility.** All LLM-free numbers (corpus, substrate, gate, foil,
statistics) are bit-exact from a clean clone — the audit reproduced the
committed Phase C table to four decimals with an independent sklearn
implementation. Mouth-dependent numbers (VERBALISED, JUDGE) are
deterministic in distribution but not bit-stable across llama.cpp GPU
runs: the audit's full regeneration measured VERBALISED AUROC2 0.5005 vs
the committed 0.4933; expect deltas of roughly ±0.02 around chance, to
which every registered verdict is insensitive. The dress-rehearsal
reports in `instruments/` are version-controlled post-freeze
regenerations at the frozen constants (the audit found the previously
shipped, unversioned CPU quick-arm report predated the C_L2/S_L2 freeze
calibration; the full-arm report was already at frozen constants — audit
A8 and its addendum); their first line is a provenance stamp added at
commit time.

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
- `audit/` — the adversarial audit: report, read-only diagnostics,
  per-item outputs. Run after publication, before any preprint.
- `notebook.md` — the append-only lab log, entries 1–18, including every
  mistake. `docs/deviation_log.md` — three deviations: 1–2 closed,
  3 (interpretation correction) pending its OSF filing. The process
  record is part of the publication.
- `docs/` — project plan, freeze checklist (every tunable + provenance),
  registration, OSF correction text.

## Honest limitations

- **ECE is reported, not optimised**: the gate's confidence is
  discriminative (AUROC2 0.979 under registered scoring) but not
  calibrated as a probability (ECE 0.159), because fitting a calibration
  map to correctness is categorically excluded by design. That trade is
  registered.
- **Exact-string queries**: every confirmatory query resolves by exact
  string identity (cosine 1.0). Paraphrased/partial/noisy phrasing was
  measured only in dev (registry resolve top-1 0.927) and is outside the
  registered claims (audit A3).
- **Ambiguity scope**: stored-d detects same-key duplicates only;
  near-duplicate keys (typo'd subjects, synonym relations) are answered
  confidently, both ways in the Lisbon/Boston-class case (audit A4). At
  the deployed thresholds the referential signal routes 47/150 clean ID
  queries to disambiguation.
- **Template fluency**: gate-governed answers are slot-filled templates
  with (verified) connective text; free generation measured 92%/23%
  fabrication-or-echo rates from a 3B mouth and is disabled on principle.
  The leak number is scoped to the checker's vocabulary (audit A5).
- **Synthetic corpus**: entities/relations are generated families
  (confusables included) with type-unmatched objects in places; no
  real-world knowledge, temporal reasoning, or multi-hop queries.
- Encoder correlation, not dimension, bounds capacity (measured; the
  D=16384 arm is kept as a negative result in the notebook).

## License

Code: Apache-2.0 (see LICENSE). OSF materials: CC-BY. Model weights are
third-party and referenced by pinned hash only.
