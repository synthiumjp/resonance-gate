# The Resonance Gate — Project Plan

**Scoped research build · v1.0 · July 2026**
Jon-Paul Cacioli · Classical Minds, Modern Machines (Synthium)

---

## 1. Objective and scope

**Objective.** Build the first memory substrate in which confidence is the retrieval geometry itself, then test — under pre-registered conditions, on the frozen artifact — whether endogenous resolution-confidence matches trained, bolted-on confidence. Deliver one preprint, one reproducible desktop demo, and released code.

**In scope:** embedding-path VSA substrate; load-normalised (b,d,u) gate; template verify-then-speak; write path with provenance + echo-check; retraction; honesty benchmark suite; desktop demo; confirmatory calibration study; preprint.

**Out of scope (explicitly, in writing, so scope creep has to argue with this document):** phone build; MCP server; residual-stream bridge (named as future work only); consolidation; memory-suite head-to-heads against tuned commercial stacks; any user-facing product commitments. Each of these is a named *possible sequel*, not a deliverable.

**Resource envelope.** Solo, part-time alongside FRV and board commitments. Planning assumption: ~10–12 focused hours/week, M3-Ultra/MLX stack. All week counts below are calendar weeks at that rate. Rule: if three consecutive weeks fall below ~6 hours, the timeline shifts right — logged, not absorbed by cutting rigor.

---

## 2. The rigor architecture: a two-phase firewall

The design that lets this survive review *and* stay buildable is a hard wall between exploration and confirmation:

**Phase E (Exploratory, weeks 1–12).** Total freedom. Tune D, θ, α, β, templates, thresholds, anything, as often as needed. Every number produced is exploratory and will be labelled as such. No hypothesis is committed. The only discipline is the **lab notebook** (append-only log of design changes and why — this later becomes the transparency appendix and is cheap insurance against "garden of forking paths" critique).

**The Freeze (week 12–13).** The artifact is version-tagged. From this commit forward: no substrate, gate, encoder, template, or tunable changes. A frozen-artifact hash goes in the pre-registration.

**Phase C (Confirmatory, weeks 13–19).** The pre-registration is filed on OSF *after* the freeze and *before* any confirmatory data is collected: hypotheses, decision rules, exclusion criteria, analysis code, seeds. Then the study runs once, on fresh stimuli never used in Phase E, and reports whichever way it falls. Deviations go in the standing deviation log.

This is the standard exploratory→confirmatory sequence done honestly, and it converts the thing that felt like a cage in v0.1 — pre-registering a system still being designed — into its correct form: pre-registering an *evaluation* of a finished system. A reviewer cannot attack the tuning (disclosed, exploratory, pre-freeze) and cannot attack the test (registered, frozen, single-shot).

---

## 3. Phase E — build (weeks 1–12)

### Stage E1: Substrate core (weeks 1–4)
- Embedding encoder (small off-the-shelf model) + fixed random projection into MAP space, D ∈ {8192, 16384}.
- Bind/bundle/permute; role–filler records (subj ⊛ ρ¹·rel ⊛ ρ²·obj); append-only on-disk cleanup store (L2); live bundle (L1).
- Read path: per-role unbind + cosine cleanup first; resonator network second, behind a feature flag, with the sequential-unbind fallback wired from day one.
- **Exit criteria:** round-trip read of written facts ≥ 99% at low load; L1 capacity-vs-SNR curve measured across k; write verified O(1).

### Stage E2: Gate + controller v0 (weeks 4–7)
- Crosstalk-normalised resolution z(a) = (a − μ(k,D,N))/σ(k,D,N) with analytic moments validated against the E1 empirical curve.
- (b,d,u) opinion; fixed-threshold controller (answer / deliberate / recollect / abstain — "recruit" degrades to plain disclosure in the offline build).
- **Exit criteria:** on dev labels, u separates in-memory from out-of-memory queries above chance with a healthy margin; d separates planted ambiguity pairs (two near-equal records) from clean singletons; gate behaviour stable across the full measured load range.

### Stage E3: Mouth + verify-then-speak + write path (weeks 6–10, overlapping)
- SmolLM3-3B frozen; template-forward factual rendering; free generation only outside gate-governed content.
- Write path: explicit-assertion extraction to triples; provenance roles (user-stated / assistant-inferred / tool-derived); echo-check on every write; supersedes-chain updates; subtract-and-tombstone retraction.
- **Exit criteria:** ungrounded-content leak ≤ 2% on a held-out grounded/ungrounded dev set; echo-check pass ≥ 99%; retraction suite green (deleted stays deleted; superseded resolves to successor).

### Stage E4: Instruments + dry run (weeks 9–12)
- Port the type-2 apparatus unchanged from prior Synthium work: seeded pseudo-2AFC mapping, AUROC2 with paired-bootstrap CIs, ECE, meta-d′/M-ratio under the 0.55–0.95 accuracy eligibility window with the Guggenmos low-d′ exclusions.
- Wire all four confidence baselines (§5) and run the entire Battery on *development* stimuli end to end — a full dress rehearsal producing exploratory numbers.
- **Exit criteria:** pipeline runs unattended, seeded, and reproducible from a clean checkout; exploratory AUROC2 for resolution-confidence at least beats the shuffled null convincingly (if it can't beat the null on dev data, freeze is postponed and the gate is redesigned — this is the one place Phase E can loop).

**Week-12 decision point.** Proceed to freeze only if all exit criteria hold. If E4's exploratory endogeneity signal is clearly absent after redesign attempts, the honest move is the negative engineering report ("resolution geometry in an embedding-projected MAP substrate does not carry calibration") — smaller paper, still publishable, and the notebook makes it credible.

---

## 4. The Freeze (weeks 12–13)

- Tag the artifact; record commit hash, model hashes, D, θ, α, β, all templates, all thresholds.
- Generate the confirmatory stimulus set: fresh in-distribution and out-of-distribution factual QA items, disjoint from every item used in Phase E, assignment seeded.
- File the OSF pre-registration: hypotheses (§6), decision rules, primary/secondary metrics, exclusion rules, analysis scripts, seeds, the artifact hash, and the standing deviation-log commitment.
- Nothing in Phase C touches the artifact. Bugs found post-freeze are logged; only a bug that *invalidates measurement itself* (not one that hurts performance) may be patched, with the patch and rationale in the deviation log and the study restarted on fresh stimuli.

---

## 5. Baselines and threats-to-validity register

Four confidence baselines, all run on identical stimuli through the identical type-2 pipeline:

1. **Verbalised confidence** of the mouth (the floor everyone must beat).
2. **Probe-to-logit controller** (Cacioli 2026a/b) — a *trained* head; the sharpest possible foil for the endogeneity claim, and mine, so no accusation of a weak-baseline strawman.
3. **LLM-judge confidence** (D-Mem-style) — the field's current default.
4. **Shuffled-resolution null** — resolution scores permuted within accuracy strata; the check that geometry, not accident, carries the signal.

**Threats register — each attack pre-answered in the preprint, drafted now:**

| Attack | Pre-built answer |
|---|---|
| "This is just a retrieval-score threshold; RAG-abstention showed those don't calibrate (Soudani et al.)" | The axiomatic dissociation requires a downstream generator with degrees of freedom; verify-then-speak removes them, so answer correctness reduces to resolution correctness + write accuracy. Plus scalar scores cannot make the u/d split. Full §-length engagement. |
| "The embedding encoder is trained, so nothing is 'endogenous'" | Claim scoped in writing to *no confidence-specific training*: geometry never fit to correctness labels. The contrast object is baseline 2, which is fit to them. |
| "Confidence tracks memory, not truth" | Acknowledged as constitutive; write path (provenance, echo-check, conservative extraction) named and measured; residual risk disclosed. All competitors share it; RG states it. |
| "Calibration will drift with memory load" | Load-normalised z(a); gate calibration is load-invariant by construction; invariance shown empirically across the measured k range. |
| "Dev-set tuning contaminated the result" | Firewall: frozen artifact hash, post-freeze registration, disjoint seeded stimuli, notebook + deviation log published. |
| "Baselines are weak" | Baseline 2 is my own published trained method; beating myself is the strongest available form of the claim. |
| "Resonator networks don't scale" | Resonator is a feature-flagged fast path; all confirmatory results run on the sequential-unbind path unless the resonator passes its own dev-set reliability bar. |
| "n too small / underpowered" | Power analysis in the pre-registration: item count set from Phase-E variance estimates to give ≥80% power for the H1 margin at α=.05, paired bootstrap. |

---

## 6. Phase C — the confirmatory study (weeks 13–19)

Registered hypotheses and decision rules (final wording fixed at registration; substance fixed now):

- **H1 (endogeneity — primary).** Resolution-confidence AUROC2 exceeds verbalised-confidence AUROC2; paired-bootstrap CI excludes zero. *Falsified → published as the negative it is.*
- **H2 (parity with a trained head — secondary).** Resolution-confidence AUROC2 falls within a pre-set margin (0.02, revisited against Phase-E variance before registration) of the probe-to-logit controller. *H1-pass + H2-fail is reported as the partial result it is.*
- **H3 (ignorance/ambiguity separation).** The u vs d decomposition classifies held-out ignorance vs ambiguity items above chance (pre-set AUC floor). *This is the metric no other architecture can report; it runs even if H2 fails.*
- **H4 (gate discipline).** Confirmatory leak rate ≤ 2% under verify-then-speak. *Failure voids the honesty claim and is reported.*
- **Secondary/descriptive:** ECE; meta-d′/M-ratio where d′ eligibility holds (dropped, not forced, otherwise); ID vs OOD breakdown; load-invariance check.

One run, seeded, on the frozen artifact. Analysis by the registered scripts. Results reported whichever way they fall.

---

## 7. Write-up and release (weeks 18–24, overlapping)

- **Preprint** (Synthium series): system description, the two-phase methodology as an explicit contribution (gate-first system-building with an exploratory/confirmatory firewall), confirmatory results, threats register as a section, limitations verbatim from the plan, notebook + deviation log in supplementary.
- **Demo:** a recorded and script-reproducible desktop session — months-scale recall (compressed via a seeded synthetic history), a plain "I don't know" on OOD, a "which one do you mean?" on planted ambiguity, a correction taking effect, network disabled throughout.
- **Code release:** substrate, gate, instruments, analysis scripts; mouth and embedder referenced by hash.
- **OSF filing** closed out: registration, data, deviation log, notebook.

---

## 8. Timeline summary

| Weeks | Phase | Milestone |
|---|---|---|
| 1–4 | E1 | Substrate core; capacity curves |
| 4–7 | E2 | Gate + controller v0 |
| 6–10 | E3 | Mouth, verify-then-speak, write path, retraction |
| 9–12 | E4 | Instruments ported; full dress rehearsal on dev stimuli |
| 12–13 | Freeze | Artifact tagged; stimuli generated; OSF registration filed |
| 13–19 | C | Confirmatory study, single run |
| 18–24 | Release | Preprint, demo, code, OSF close-out |

~6 months part-time end to end. Slack policy: schedule slips right before rigor is cut; the deliverable set never grows mid-project (additions become named sequels).

## 9. Standing risks

1. **Time volatility** (FRV, board): absorbed by the slip-right rule; the firewall means a pause never contaminates the design–test separation.
2. **E4 finds no signal:** the pre-planned off-ramp is the negative engineering report; the notebook makes it publishable.
3. **Field moves during the build:** monthly literature sweep logged in the notebook; positioning updated in the preprint, design frozen regardless — a competing preprint changes the related-work section, not the study.
4. **Scope temptation** (MCP server, phone, bridge): each is pre-named as a sequel in §1; adding one requires amending this document first, which is the friction that keeps the project finite.
