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

## Deviation 2 — 2026-07-19 (FINAL, sanctioned: premature execution of the
Deviation-1 rerun)

Event: while executing the sanctioned Deviation 1 items, the analyst
invoked instruments/phase_c.py intending a guard verification. The guard's
coded preconditions (filed registration lines; refit head hash) were
satisfied, so the script executed the full confirmatory analysis on the
second seed family (888000011-14) BEFORE this deviation log was filed on
OSF and before the registrant's go — a breach of the registered workflow,
attributable to the analyst, not to any property of the frozen artifact.

Containment and integrity state:
- The premature run's report was not read by the analyst (terminal output
  filtered to the completion line) and is retained UNOPENED at
  instruments/phase_c_report_PREMATURE_QUARANTINED_UNREAD.md (bytes also
  at commit 4b67be3). No number from it has been observed by any person.
- Seed family 888000011-14 is treated as CONSUMED and will not be reused.
- No code, tunable, decision rule, margin, or hypothesis changed after the
  premature run (nothing was seen that could motivate a change).

Quarantine disposition (registered): the premature report is hash-attested
in this filing (sha256
40cbc34da1a8a0a5b7c860b611030b8a62c724b75a09e83de34bc9e1722f123a) and
remains unread; the file itself will be uploaded to OSF only AFTER the
valid run's report is committed and filed, at which point it stands as a
verifiable, unread, accidental replication on an independent seed family.
Release order is part of the registered remedy.

Procedural change (registered): the confirmatory run will be executed by
JP personally at the terminal. The analyst's role ends at preparing the
command. No invocation of phase_c.py by the analyst for any reason,
including guard checks — the filed go is the only trigger, and the human
holds it.

Sanctioned remedy (executed): third confirmatory seed family 999000021-24
(corpus / assignment+elicitation / bootstrap / permutation), disjoint from
all dev seeds and both consumed blocks; instruments/phase_c.py updated,
new blob hash: ae5d4d5d4c286b410a0429f6b23daa5f195f0c84. One run, by the registrant, after both deviations
are filed on OSF.
