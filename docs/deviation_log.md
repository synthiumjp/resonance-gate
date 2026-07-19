# Deviation log — RG confirmatory study (OSF https://osf.io/95e2q/)

## Deviation 1 — 2026-07-19 (measurement-invalidating instrument bug; DRAFT
pending decision, no patch applied yet)

Event: the single registered Phase C run (seeds 777000001-4) executed
immediately after filing. Verbatim outcome recorded in
instruments/phase_c_report.md (committed, labelled INVALIDATED-H2):
H1 PASS (+0.3811, +0.5240); H2 "PASS" VACUOUS (see below); H2b PASS
(0.3910, 0.5256); H3 PASS (1.0000/1.0000); H4 PASS (0/61); GATE(1-u)
0.9619 (0.9357, 0.9823); permutation p<0.001.

Bug: the frozen H2 foil head (instruments/h2_foil_head.json) standardises
features by training sd with a 1e-9 floor. Features k and N were CONSTANT
on the dev corpus (235 / 500), so their sds froze at 1e-9. On the
confirmatory corpus (k=236) the standardised k feature is (236-235)/1e-9
= 1e9, the logit saturates at -2.8e6, and the head outputs exactly 0.0
for all 280 items -> FOIL AUROC2 = 0.5000 with zero-width CI. The H2
comparison measured a numerical artifact, not the trained readout.
Classification: bug that invalidates measurement itself (plan section 4),
in instruments/ (analysis apparatus); no frozen substrate/gate/encoder/
mouth code is implicated.

Prescribed remedy (plan section 4, pre-registered): minimal patch +
rationale here; study RESTARTED on fresh stimuli with a new registered
seed family. Proposed minimal patch: LogisticProbe.fit drops zero-variance
features (weight fixed 0) instead of flooring sd; refit the foil on the
UNCHANGED dev corpus; re-freeze head with new hash; update the registration
addendum with the new hashes and seed family. Seeds 777000001-4 are
consumed and will not be reused.

Status: AWAITING DECISION — patch and restart require sanction and an OSF
deviation filing by the registrant.
