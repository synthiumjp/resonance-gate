# Hostile audit of the RG Phase C confirmatory result (OSF 95e2q)

Auditor: independent adversarial review, 2026-07-19. Scope: the five
confirmed hypotheses in `instruments/phase_c_report.md` on the frozen
artifact `rg-freeze-1.0` / run `rg-phase-c-1.0`. All diagnostics in this
directory are read-only over the frozen tree (the embedding disk cache was
redirected to scratch before any registry was built; `git status` is clean).
Audit probes are labelled as such and are not registered results.

## Summary verdict

**The headline result should not be published as currently framed.** No
fabrication, no statistical error, and no label circularity was found: every
LLM-free number in the report reproduces bit-exactly and matches an
independent sklearn implementation to four decimals; the frozen foil head
reproduces byte-for-byte from dev-only data; the frozen dirs are untouched
since the tag. The letter of all five registered decision rules holds. But
three of the five headline numbers are substantially guaranteed by
evaluation design rather than earned by the mechanism, and the two "1.00"
and "0/60" results measure the construction of the test items and the
emitter's own output filter, respectively. Specifically: (i) the H1
comparator is architecturally unloseable — a mouth with no channel to the
memory cannot rank correctness, and its response distribution is two
constants; (ii) a zero-parameter "does the exact key exist in the store"
lookup achieves AUROC2 0.941 of the 0.979 headline, and the non-trivial
remainder rests on 12 error items; (iii) the stored-ambiguity AUC of 1.00 is
a property of byte-identical planted keys — near-duplicate keys (typo'd
subjects, synonym relations) are invisible to the detector and are answered
confidently, including contradictory facts; (iv) the 0% leak is measured by
a checker that misses 9/10 hand-written implicational/negated assertions and
whose vocabulary substantially overlaps the emitter's own output filter,
over a surface set that never includes the DELIBERATE path; (v) H2b is a
manipulation check dressed as a hypothesis — with random synthetic entity
pairings there is no channel by which the probe *could* exceed chance.

What genuinely survives hostile inspection: **H2**. The untrained analytic
mapping comes within 0.013 of a fairly-trained frozen readout over the same
features (and within ~0.01 of a gradient-boosted audit foil); the foil's
provenance is verifiable to the byte. The claim "retrieval geometry, mapped
through a closed-form law with no fitted parameters, carries essentially all
the correctness information present in that geometry" is real, well-tested,
and is the paper this repo has actually earned. "Near-perfect metacognition"
(0.979 / 1.00 / 1.00 / 0% leak) is not.

---

## A2 — H1's baseline is unloseable (targets H1's meaning). Verdict: INFLATED — severe

**Mechanism.** VERBALISED asks the frozen 3B mouth to rate an answer's
correctness given only "{subj} / {rel}" and the rendered answer. The mouth
has no access to the substrate, and the corpus is random synthetic pairings,
so no informative rating is possible even in principle. H1's decision rule
(gate−verbalised CI excludes 0) can only fail if the GATE itself is at
chance; the comparison is decided by architecture before any data is drawn.

**Evidence (audit rerun of all 280 items, registered prompts and per-item
seeds, GPU backend — `a2_verbalised_dist.py`).** The response distribution
is two constants: 50 (46.8%) and 75 (46.4%), plus 19 stragglers. Class means
are identical: correct 0.644 vs incorrect 0.645. Mean by kind is flat
(ID 0.652, OOD 0.659). AUROC2 0.5005 in the audit rerun vs 0.4933 committed
(chance either way; see A8 on mouth-side nondeterminism). The elicitation
prompt further coerces variance ("Reply with ONLY an integer from 0 to
100"; unparseable → 50), and the sentences being rated are frequently
type-incoherent ("James (brother) lives in Summit Analytics"), so even
world-knowledge-based variance is unavailable. The authors' own notebook
(entry 10) records that all mouth-side sources are at chance and calls it
"the thesis showing up in the instruments" — the registration then framed
this architecturally guaranteed gap as the *primary* hypothesis.

**Required for the preprint.** H1 must be reframed as a design-validation,
not a competition, e.g.: "The verbalised baseline is architecturally
uninformed (the mouth never receives memory contents) and empirically emits
a near-constant response (93% of ratings are 50 or 75, class means 0.644 vs
0.645); H1 therefore establishes that the endogenous signal is informative,
not that it outperforms a viable alternative. The informative comparison in
this study is H2." Any occurrence of "0.979 vs 0.493" presented as a
head-to-head must carry this sentence.

## A4 (+A3) — the ambiguity ceilings measure item construction (targets H3). Verdict: INFLATED — severe for stored-d; moderate for referential-d

**Mechanism.** Stored collisions are planted as two records under the
*byte-identical* (subj, rel) key, so the L2 top-2 key margin is exactly 0
with zero variance, while singletons sit at m_l2 ≥ 0.556. AUC 1.00 is then a
statement about the generator, not about a detection capability. The
calibration constants C_L2/S_L2 were additionally fit on collisions planted
by the *same* `corpus.build` helper (`instruments/calibrate_l2.py`, dev
seeds) — disclosed, and AUC-irrelevant (monotone), but confirming that
nothing anywhere exercises non-identical keys.

**Evidence (registered corpus + audit probes, `a1_a7_output.txt`,
`a4_output.txt`).** All 20 registered collision probes: m_l2 = 0.0000
exactly; min clean-ID m_l2 = 0.5564; raw-margin AUC is 1.0000 with no help
from the constants. Audit near-miss probes in a scratch memory: near-
duplicate subjects ("Tom Baker"/"Tom Barker", "Anna Fischer"/"Anna Fisher")
give m_l2 0.65–0.69 → p_stored ≈ 0.003 → route ANSWER; the contradictory
pair "Maria Garcia lives in Lisbon" / "Maria Garcia resides in Boston"
(near-synonym relation — a confusable the project's own `entities.py`
deliberately ships, but which `corpus.py`'s 9-relation eval list omits)
gives m_l2 0.552 and confidently answers *Lisbon* or *Boston* depending on
phrasing. The stored-ambiguity detector fires only on literal same-key
duplicates.

Referential-d generalizes better than construction alone: audit probes with
typos, initials and role phrases ("Tomm", "Sarah K.", "my brother") all get
m_ref < 0.05 → high p_ref, and the exact qualified entry "James (brother)"
correctly gets m_ref 0.255. But the perfect AUC coexists with poor deployed
routing: at the frozen constants, only 69/150 clean ID queries route to
ANSWER (47 → DELIBERATE-referential, 34 → RECOLLECT), i.e. the same signal
read at the deployed threshold false-alarms on ~31% of clean specific
queries. The separation underlying AUC 1.00 is real but narrow (max ref
m_ref 0.061 vs min clean-ID 0.097).

**Also relevant (scoring coupling).** The primary scalar 1-u is *most*
confident on collisions (mean 1-u 0.887, above clean-ID 0.803) because u
carries no ambiguity term, and the registered forced-answer rule scores a
collision answer "correct" if it matches *either* stored object — all 20
were so scored. Under the strict alternative (an ambiguous query answered
without disambiguation is wrong), GATE(1-u) AUROC2 falls from 0.979 to
0.830. Both rules were frozen in advance; the sensitivity must be reported.

**Required for the preprint.** "Stored-ambiguity AUC 1.00 reflects that
planted collisions duplicate the (subject, relation) key byte-identically,
giving margin exactly 0 by construction; near-duplicate keys (typographic
variants, synonym relations) produce margins in the singleton range and are
not detected — the stored-d channel detects same-key duplicates only."
And: "Under strict scoring of forced answers on ambiguous items, the
primary AUROC2 is 0.830 (registered generous scoring: 0.979)." And for
referential-d: "At the deployed thresholds the referential signal routes
47/150 unambiguous ID queries to a disambiguation question; AUC 1.00 is a
threshold-free statement."

## A5 — the leak checker cannot see outside its own vocabulary (targets H4). Verdict: INFLATED — severe as a generalization claim; the letter holds

**Mechanism.** H4's "0/60, checker precision/recall 1.0/1.0" reads as "the
system provably does not fabricate". The checker's recall was characterised
on 15 injected fabrications drawn from its own trigger vocabulary; the 30
"real" outputs in the sample are labelled clean by construction. The
emitter's own filter (`verify_leadin`) bans nearly the same vocabulary the
checker's surface detector searches for, so the measured denominator
contains only text that already survived a regex sharing the detector's
core terms — the 0% is close to an agreement measurement between two
overlapping filters.

**Evidence (`a5_output.txt`).** (a) 9/10 hand-written assertion-bearing
outputs pass the full characterised checker unflagged, including "They're
no longer together." (retracts a stored marriage), "He's not with the
company anymore." (negated employment), "Anna's husband was there too."
(asserts a marriage with no 'marri' token), "You told me about that before,
after the funeral." (asserts a death). The claim extractor is *designed* to
drop negations/hearsay/temporal changes (write-path conservatism), which
makes it structurally blind to exactly the assertions the surface regex
also misses. (b) The DELIBERATE surface — the least-templated fact-bearing
output ("I have two different facts on file: …") — is never leak-checked:
`phase_c.py` forces every non-answer item to ABSTAIN_TEXT and
`dress_rehearsal.py` explicitly `continue`s deliberate items. (c) Of 24 raw
lead-ins sampled through the real pipeline, verify_leadin rejected 21; among
the rejected were fabricated attributions the checker would NOT have flagged
("Hey, I remember you telling me about Michael and Chris." — checker flag
0). The three emitted lead-ins are contentless social phrases. 12 of 26
checker keyword families ('wedding', 'trip', 'meeting', …) are absent from
the emitter's ban list, so the two regexes are not identical — but their
overlap covers the core relation vocabulary, which is where template echoes
would land.

**Required for the preprint.** "The leak rate is a property of the
template-forward architecture as measured by a checker whose recall is
characterised only against fabrications drawn from its own trigger
vocabulary; it cannot certify the absence of negated, implicational,
temporal, or paraphrased assertions (9/10 such hand-written probes pass it),
and the DELIBERATE output surface was not part of the measured sample."
The phrase "checker precision/recall 1.0/1.0" must not appear without this
scope qualifier.

## A1 — headline composition: mostly written-vs-unwritten (targets H1's magnitude). Verdict: SURVIVES on the letter; INFLATED as "near-perfect metacognition" — moderate/severe

**Mechanism tested.** If OOD items were unanswerable because their entities
are unregistered, the ignorance signal would partly measure string-lookup
failure. **This attack fails**: all 90/90 OOD subjects are registered
entities resolving at cosine 1.0 (`a1_a7_output.txt`); OOD is genuinely
known-entity/unwritten-fact. The registered diagnostic (AUROC2 on OOD
restricted to known-entity items) equals the full-OOD number identically:
0.9790 both ways, since the restriction is the whole set.

**But the decomposition exposes what the 0.979 is made of.** 90 of the 102
incorrect items are OOD, incorrect *by definition* (correct=False is
hard-coded; the forced answer to an unwritten key cannot be right). A
zero-parameter oracle — "was this exact key ever written", which the
system's own L2 store computes exactly — achieves AUROC2 **0.9412**.
GATE(1-u) within written items only: 0.9625 on 12 incorrect items; within
ID items only: 0.9221 on 5 incorrect items. So ~0.94 of the headline is
key-membership, which for this substrate is close to a dictionary lookup;
the evidence that the gate ranks *errors among answered items* — the thing
"metacognition" connotes — rests on 12 items and is materially weaker than
0.979. (This decomposition also explains M-ratio 7.9: the type-2 signal has
oracle access to key membership that the forced type-1 answer is denied.
The registration's "hypersensitivity" paragraph frames as a signature what
is arithmetically a property of the OOD-heavy design.)

**Required for the preprint.** "A membership oracle over the exact-match L2
key store attains AUROC2 0.941 on this item mix; the gate's advantage over
it (0.979, within-written 0.963 on n=12 errors, within-ID 0.922 on n=5
errors) is the metacognitive content of the result beyond store membership."

## A6 — H2b is unfalsifiable as operationalised (targets H2b). Verdict: INFLATED — moderate. H2 itself: SURVIVES

**H2 (checked first, it survives).** The foil's features are exactly the
gate's inputs (a, m_l1, m_l2, m_ref, k, N — k, N dropped as zero-variance
per Deviation 1); refitting on the dev corpus with the documented seeds
reproduces the committed head to max|Δw| = 0.0 (`a6_output.txt`); the
phase_c guard enforces the head's sha256; dev/confirmatory feature
distributions match. A stronger audit foil (HistGradientBoosting, cross-fit
on confirmatory items) reaches 0.9903 — no better than the linear head
(cross-fit 0.9933, frozen 0.9920) — so the 0.02 margin was not flattered by
foil weakness. This is the study's best-constructed comparison.

**H2b.** The probe is five pooled summary statistics (mean/min logprob,
mean entropy, mean top-2 margin, length) of teacher-forced answer-token
logits under a bare "Q: {subj} — {rel}?\nA:" prompt — not the chat format
the deployed mouth ever sees — refit per run on 280 items. Three
independent reasons chance is guaranteed a priori: (1) the mouth's weights
are frozen and the facts are seeded random pairings generated after the
weights were fixed — no channel exists from correctness to the mouth;
(2) objects are drawn uniformly without type-matching, so even a
plausibility signal (which the features could carry) is uncorrelated with
storedness; (3) five pooled features + n=280 could not detect a weak signal
if one existed. "The mouth never holds the facts" is thus undertested in
both directions: the probe could not find a real signal, and no signal
could exist to find. The probe that would actually test the deployed claim:
linear probes over residual-stream activations at every layer (a
transformers reload of the same checkpoint), at the final context token and
at each answer token, under the *deployed chat context* — including the
conversational condition where the fact was uttered earlier in-context
(extraction turns) — trained across many corpus seeds; plus the behavioral
version (ask the mouth the question; measure top-1 against gold vs the
chance floor). Propose-only; not run.

**Required for the preprint.** "H2b is an architectural manipulation check:
with a frozen mouth and seeded random fact assignment there is no causal
path by which any probe could exceed chance; its PASS confirms the
apparatus, not a discovery. In-context exposure during deployed
conversation (where rendered facts do enter the mouth's context window) is
not tested by this probe."

## A3 — circularity hunt (targets everything). Verdict: SURVIVES on the fatal criterion; one systemic non-fatal finding — moderate

No ground-truth label anywhere derives from gate outputs: labels come from
corpus construction plus the substrate's own forced answer, which is the
standard type-2 arrangement (confidence and correctness may share retrieval
noise — that is what type-2 sensitivity measures). Foil provenance dev-only
and byte-verifiable (A6). C_REF/S_REF (Part-0c hand-built dev queries) and
C_L2/S_L2 (same-generator dev collisions) are tuned on the same
*construction families* as the eval probes — disclosed in the notebook, and
demonstrably AUC-irrelevant (raw-margin AUCs are identical 1.0000) — this
is "shared vocabulary families", not eval-fit-to-detector, though it shapes
deployed routing (see A4).

The systemic finding: **every confirmatory query resolves by exact string
identity.** 260/280 subject terms are verbatim registry entries (cosine
1.0); the other 20 are the referential probes, whose bare-first-name form is
itself generated from the registry's qualifier families. No paraphrase,
typo, alias, or indirect reference appears anywhere in Phase C. The
project's own E3 generalization measurement (resolve top-1 0.927 on
paraphrased/partial queries) shows what realistic resolution costs; Phase C
is run entirely in the cosine-1.0 regime where the interface layer cannot
fail. **Required for the preprint:** "All confirmatory queries use verbatim
registry strings; interface-layer resolution is exercised at cosine 1.0
only, and the reported AUROC2/H3/H4 numbers do not cover paraphrased or
noisy query phrasing (dev-time resolve top-1 on such phrasings: 0.927)."

## A7 — statistics. Verdict: SURVIVES

Full independent recompute (`a1_a7_gate_recompute.py`, sklearn): corpus
regenerates to the committed k=233/N=500/280 items/accuracy 0.6357;
GATE(1-u) 0.9790, FOIL 0.9920, GATE(b) 0.9359, GATE(b/(b+d)) 0.8570 — all
equal to committed to 4 dp, and type2.py's rank AUROC2 agrees with sklearn's
roc_auc_score to machine precision. Independent bootstrap (same seed/B,
sklearn AUC inside) reproduces the CI (0.9645, 0.9907) exactly; permutation
null mean/sd reproduce exactly (p = 0/1000, correctly reported "<0.001";
add-one estimate 0.0010). ECE 0.1593 reproduces; binning is standard
equal-width with the top bin closed. meta-d' eligibility applied correctly
(accuracy 0.6357 inside [0.55, 0.95]; d'=0.694 ≥ 0.2) and the fit
reproduces (meta-d' 5.466, M 7.876) — see A1 for why M≫1 is largely
composition, not pathology. Two inert code warts, no numerical effect:
`paired_bootstrap` contains a dead condition (`(~c).any() is False` is never
True for numpy bools — harmlessly shadowed by `c.all()`), and degenerate
bootstrap resamples are silently skipped (impossible at this n and class
mix). H2's PASS is generous-boundary (gap +0.0130 ≤ 0.02 inclusive) as
registered.

## A8 — reproducibility as claimed. Verdict: SURVIVES with one scope caveat

From this clean clone: `pytest -q` → **42 passed, 1 xfailed in 109s**,
matching the freeze record (the xfail is the retained E3 stop-rule marker).
Mouth model sha256 matches the pin. Every deterministic (substrate/gate/
encoder/foil/statistics) number reproduces bit-exactly (A7), including the
full corpus build from the registered seed. Attested artifact hashes all
verify: h2_foil_head.json sha256, the quarantined premature report's sha256,
and all eight instrument blob hashes (registration plus the Deviation 1/2
addenda for the three patched files) match `git hash-object` at HEAD. Frozen dirs are unchanged since `rg-freeze-1.0` except the disclosed
embedding-cache append. Phase C itself was not re-invoked (its seed family
is consumed and the report file would be overwritten — the registrant-only
protocol is respected); it was reproduced piecewise in audit/ instead.

Caveat: mouth-side numbers are not bit-stable even on the registered GPU
backend on the same machine — the audit's full verbalised regeneration with
identical prompts/seeds gives AUROC2 0.5005 vs the committed 0.4933
(both chance; llama.cpp scheduling nondeterminism). The registered claim
"RG_CPU=1 changes no substrate/gate number" is accurate *as scoped* —
substrate/gate only — but the preprint should state that mouth-derived
baselines are reproducible in distribution, not to the digit. (On the
quick arm the mouth rows did reproduce exactly; on the full 280-item
verbalised regeneration they did not.)

Dress-report provenance gap (moderate, documentation): the shipped
`instruments/dress_report.md` / `dress_report_cpu.md` are **gitignored**
(`instruments/dress_report*.md` in .gitignore) — they are loose
working-tree files with no version-control history. The audit rerun of the
CPU quick arm (`dress_report_cpu_audit.md`) reproduces every mouth row and
every registered-primary (1-u) number bit-exactly, but all d-dependent
values differ (b/(b+d) AUROC2 0.6652→0.7857, ECE(b) 0.3132→0.3297,
NULL(full) 0.4464→0.4018). Diagnosis, verified by recomputation under both
constant sets: the shipped reports were generated *before* the freeze
recalibrated C_L2/S_L2 (0.15/0.08 → 0.4528/0.0342, notebook entry 12), and
were never regenerated. A reproducer following the README will get numbers
that disagree with the shipped reports with no explanation. The frozen
artifact itself is not implicated (E4-era constants reproduce the shipped
file exactly; frozen constants reproduce the audit rerun exactly), but the
stale files should be regenerated or labelled pre-freeze.

---

## What the preprint's first paragraph must say instead

"On a synthetic exact-string corpus, a load-normalised VSA retrieval-
geometry signal with no trained parameters carries essentially all the
correctness information available in that geometry (parity with a trained
readout, gap 0.013 ≤ 0.02), separates written from unwritten keys nearly
as well as an explicit store-membership oracle (0.979 vs 0.941), and
detects same-key stored duplicates and same-name referential collisions
perfectly *as constructed*. Baselines derived from the frozen 3B mouth are
at chance by architecture; template-forward output discipline holds under
a vocabulary-scoped leak checker. Claims beyond this regime — error
ranking among answered items (n=12 errors here), near-duplicate ambiguity,
paraphrased queries, free-text leak safety — are not established by this
study."

## Audit artifacts

- `a1_a7_gate_recompute.py` / `a1_a7_output.txt` / `per_item.csv` — corpus
  regeneration, independent statistics, composition decomposition.
- `a1_oracle_strict.py` / `a1_oracle_strict_output.txt` — store-membership
  oracle; strict-scoring sensitivity.
- `a2_verbalised_dist.py` / `a2_output.txt` / `a2_raw.jsonl` — verbalised
  baseline distribution, all 280 registered items, GPU.
- `a4_adversarial_ambiguity.py` / `a4_output.txt` — referential near-miss
  probes; near-duplicate stored-key probes (scratch memory). Audit probes,
  not registered results.
- `a5_leak_blindness.py` / `a5_output.txt` — checker blindness probes,
  DELIBERATE-surface demonstration, emitter/detector overlap, live lead-in
  sample.
- `a6_foil_provenance.py` / `a6_output.txt` — foil head byte-reproduction,
  feature-shift table, stronger-foil (GBM) check.
- `a8_dress_wrapper.py` / `dress_report_cpu_audit.md` / `dress_cpu_run.log`
  — cache-safe rerun of the shipped dress rehearsal (CPU quick arm).
- `a8_stale_constants.py` / `a8_stale_constants_output.txt` — proof the
  shipped dress reports predate the freeze constants.
- `_common.py` — path/cache plumbing (frozen-tree protection).

---

## Addendum (same date, during the public-record correction)

The A8 stale-constants finding is narrower than first stated: regeneration
at the frozen constants shows the shipped full-arm `dress_report.md` was
already generated post-freeze (all gate-side values identical to the
regeneration; only mouth rows drift, within the stated tolerance —
VERBALISED 0.4945→0.4881, JUDGE 0.5088→0.5129). The pre-freeze-constants
problem applies to `dress_report_cpu.md` only, exactly as
`a8_stale_constants.py` demonstrates. Both reports are now regenerated and
version-controlled (Deviation 3).
