# Post-registration adversarial audit — interpretation correction

Project: The Resonance Gate (OSF 95e2q). Date: 2026-07-19.
Filed by the registrant as an update to the registration. Attachments:
`audit/AUDIT_REPORT.md` (audit commit 036dc5a in the public repository)
and `docs/deviation_log.md` (Deviation 3).

## Statement

After publication of the confirmatory result and before any preprint,
the project itself commissioned and ran an adversarial audit of the
registered Phase C analysis. The audit was conducted against the frozen
artifact (`rg-freeze-1.0`) in read-only mode, with all diagnostics
published in the repository under `audit/`.

**Registered analyses and numbers are unchanged and verified.** The
audit reproduced every LLM-free registered value bit-exactly from the
registered seeds and confirmed them to four decimals with an independent
reimplementation (scikit-learn) of the AUROC2, bootstrap, permutation,
ECE, and meta-d′ computations. All attested artifact hashes (frozen foil
head, quarantined report, instrument blobs) verify; the frozen tree is
untouched since the freeze tag; the foil head reproduces byte-for-byte
from dev-only data. The registered letter of H1–H4 and H2b stands.

**Three interpretations are corrected** (full text in Deviation 3):

1. **H1 (endogeneity).** The verbalised comparator is architecturally
   unloseable: the mouth has no channel to the memory contents, and its
   response distribution is near-constant (93% of ratings are 50 or 75;
   class means 0.644 vs 0.645). H1 stands as a design validation — the
   endogenous signal is informative — not as a competitive comparison.
   Additional disclosure: a zero-parameter exact-key store-membership
   oracle attains AUROC2 0.941 of the 0.979 headline, and under strict
   scoring of forced answers on ambiguous items the headline is 0.830
   (registered either-object scoring: 0.979). The oracle decomposition
   also accounts for the large M-ratio (7.9) as a property of the
   OOD-heavy design.

2. **H3, stored-d.** The stored-ambiguity AUC of 1.00 reflects item
   construction: planted collisions duplicate the (subject, relation)
   key byte-identically, giving a margin of exactly 0. Audit probes show
   near-duplicate keys (typographic variants, synonym relations) are not
   detected; in the synonym-relation case the system confidently answers
   both ways on contradictory stored facts. The registered claim is
   therefore scoped to same-key duplicate detection.

3. **H4 (gate discipline).** The 0/60 leak rate stands as measured but
   is scoped to its checker: the checker misses 9/10 hand-written
   negated/implicational/temporal assertions, its recall was
   characterised against fabrications drawn from its own trigger
   vocabulary, that vocabulary substantially overlaps the emitter's own
   output filter, and the DELIBERATE output surface was not in the
   measured sample. The number certifies template discipline under a
   vocabulary-scoped checker, not the absence of fabrication in general.

**What survived adversarial attack:** H2 in full — the untrained
closed-form mapping of retrieval geometry comes within 0.013 AUROC2 of a
supervised readout trained on the same features (registered margin
0.02), the readout's dev-only provenance is verified to the byte, and a
stronger gradient-boosted audit foil does no better. H2 is now presented
as the study's headline result. All statistics and the reproducibility
claims survive as scoped (mouth-dependent baseline values reproduce in
distribution, not to the digit: audit regeneration 0.5005 vs committed
0.4933, with all verdicts insensitive to deltas of this size).

The audit was conducted by the project itself prior to any preprint; the
corrected framing is live in the public repository (README, Deviation 3)
as of this filing. No registered number, seed, decision rule, or
analysis changed.
