# Deviation log — RG confirmatory study (OSF https://osf.io/95e2q/)

## Deviation 1 — 2026-07-19 (FINAL, sanctioned; supersedes the draft)

Event: the single registered Phase C run (seed family 777000001-4)
executed immediately after filing. The H2 foil head emitted a constant
(AUROC2 0.5000, zero-width CI): features k and N were constant on the dev
corpus, their training sds were floored at 1e-9, and the confirmatory
corpus's k=236 standardised to 1e9, saturating every logit. The H2
comparison measured a numerical artifact, not the trained readout —
a bug that invalidates measurement itself (plan section 4). No frozen
substrate/gate/encoder/mouth code is implicated.

SEEN-RESULTS ACKNOWLEDGMENT (Rider 1): the invalidated run's full report
was observed and is retained in the public record (commit 7b61ddb,
instruments/phase_c_report.md; it will be uploaded to OSF alongside this
deviation — nothing buried). NO decision rule, margin, scalar, threshold,
or hypothesis changes in response to anything observed in it. The only
deltas in this addendum are: the patched instrument script hashes, the
refit foil-head hash, and the fresh seed family. Everything else in the
registration stands verbatim.

MARGIN DISCIPLINE (Rider 2): the refit foil's dev gap is 0.0183
(foil cross-fit 0.9750 vs analytic 1-u 0.9567); the registered 0.02
margin is retained unchanged. If the refit predicts H2 failure, we run
anyway and report the failure.

Patch (instruments-side only): LogisticProbe.fit now DROPS zero-variance
features (weight fixed 0) instead of flooring sd. The foil was refit on
the UNCHANGED dev corpus (seed 20260719, same config, train seed 991):
dev cross-fit AUROC2 0.9750 (in-sample 0.9781) — identical to the
pre-patch dev value, as expected (the dropped features carried no dev
signal).

Addendum deltas (all other registration content stands verbatim):
- instruments/baselines.py blob: 4002ee09f443a4ee058f47d65a1044a26b7b1b79
- instruments/h2_foil.py blob: eb3383cfcaf5e320026ac9b04ac87937750e3d26
- instruments/phase_c.py blob: c4abb807c30fbff4907526e1bef3b3cd6c5385f9
- instruments/h2_foil_head.json sha256:
  702e789c57f0e67fcb83989794f3e19ad4130be42eb93de6f61760bd739df1a5
  (replaces b068c096...)
- Confirmatory seed family, second block: corpus=888000011,
  assignment/elicitation=888000012, bootstrap=888000013,
  permutation=888000014. Disjoint from every dev seed (notebook entries
  5-12) and from the consumed block 777000001-4, which is never reused.

Status: patch executed and committed; Phase C rerun BLOCKED until the
registrant confirms this deviation is filed on OSF and gives the go.
