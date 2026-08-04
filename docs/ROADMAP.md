# RG upgrade plan

Sequenced by *measured pool size × evidence that the mechanism works*, not by
conceptual appeal. Every item carries a pre-registered bar and a stop rule.
Items are gated: nothing downstream starts until the gate above it resolves,
because several proposals depend on tiers that are still being judged.

## Gate 0 — in flight (nothing new starts until these land)

| Run | Decides | ETA |
|---|---|---|
| Official round 5 | Whether retrieval v3 + as-of replaces the 52.6/19.1 headline | ~30 h |
| Gist screen (Generalization, n=112) | Whether the gist tier survives at all | **RESOLVED 2026-08-03: FAILED** (33.9 → 29.5 correct; bar was ≥+5). Tier archived. |

**Stop rule:** if the gist screen does not improve Generalization, the gist
tier is archived, and every gist-dependent item below (U3) is cancelled — not
deferred. Causal and temporal gists inherit the failure of plain gists.

---

## U1 — Typed negation *(CLOSED NEGATIVE 2026-08-03)*

**Result.** The premise was falsified before building: of 31 failing
negation questions, 22 already had the corrective content in context and
19 were answered "Unknown" — the anti-facts were not missing. A redirect
to a *targeted* yes/no premise rule (98 detectable questions) then failed
its bar: +0.2 correct for +2.1 hallucination. This refined the project's
central law: the axis is **selection vs assertion**, not global vs
targeted. Selection guidance is 2 for 2; assertion guidance is 0 for 7.
The grounding contract is now closed to further assertion rules.

*Original plan, for the record:*

**Why first.** Largest measured pool with an unbuilt, well-evidenced
mechanism. 75 dev questions carry negation golds ("Did she express
disinterest in X?"); ~31 still fail. Entry 133 banked the mechanism —
NegEx-style trigger detection plus WordNet's 7,604 curated antonym pairs —
and never built it. Rule-based negation detection is one of the few areas
where deterministic methods still beat trained ones on generalisation.

**Build.** Extraction emits *anti-facts*: `polarity: negative` on
subject/attribute/value ("does not drink coffee"), stored with the same
receipts and tiers. Retrieval surfaces them; the grounding contract gains one
clause — an explicit anti-fact answers a positive question with a correction,
not an abstention.

**Cost.** Extraction prompt change + re-extraction of dev caches (~2 GPU-h) +
one judged screen.

**Bar (pre-registered).** On the negation-gold subset: ≥+5 correct with
hallucination not worse than +1. Memory Boundary must not degrade.

**Risk.** Anti-facts are assertions; a false anti-fact is a hallucination
with a receipt. Mitigation: anti-facts require explicit negation triggers,
never inference from absence.

---

## U2 — Receipt operations *(SHIPPED 2026-08-04, ranking half declined)*

**Result.** Operations shipped non-destructively (strengthen / salience /
merge / split / invalidate / dynamics) and exposed as MCP `profile_dynamics`.
The retrieval-ranking half was measured and declined: salience-weighted BM25
moved gold-in-top-5 by +1.1pt at best (19.8% → 20.9%), which is inside the
churn band entry 145 established, so no judged screen was run and salience is
not wired into the answer path. Prior held (entry 100: corroboration count
carries no correctness signal on this benchmark).

*Original plan:*

**Why second.** Cheap — most of it assembles from `spacing.py` and existing
receipt fields — and it is what makes the memory *behave* like memory rather
than a log.

**Build.** Promote receipts from metadata to objects with operations:
`strengthen` (re-observation), `decay` (unreinforced provisional facts lose
salience without deletion), `merge` / `split` (cluster corrections),
`invalidate` (owner correction, already partly present). Retrieval ranking
gains a recency/decay term; `profile_status` reports memory dynamics.

**Cost.** Pure Python, no GPU. One deterministic A/B on retrieval ranking,
one judged screen only if the deterministic pass is positive.

**Bar.** Deterministic: gold-in-top-5 must not fall. Product: decayed facts
must remain recoverable and auditable.

**Note.** mem0 ships search-time recency boost/dampen; this is the receipted
version of the same idea, and it is the mechanism our own corroboration
finding (entry 137: spacing consolidates errors too) says must be evidence
metadata rather than a truth signal.

---

## U3 — Higher-order gists *(CANCELLED 2026-08-03)*

The gist screen failed its bar (Generalization 33.9 → 29.5 correct;
hallucination flat, omission up — abstraction competed with the episodes
rather than orienting the composer). Per the Gate 0 stop rule this is
cancelled, not deferred: higher-order gists inherit the failure of plain
ones. Archived for the record, the proposal was: causal gists (cluster on the
*reason* clause our v5 extraction already preserves, not on the value) and
temporal gists (cluster episodes by period → "X does Y during busy periods").
Both keep the receipt requirement of ≥2 cited episodes.

**Bar.** Same as U1: ≥+5 correct on Generalization with hallucination ≤+1,
over and above plain gists.

---

## U4 — Event-typed facts *(deferred, with reasons)*

Structured events (`subject / action / object / date / reason`) would improve
Dynamic Update and conflict detection. Deferred, not declined, because the
arithmetic does not support doing it first: Dynamic Update is 20 dev
questions (103 official) against Generalization's 112 (371), the as-of prompt
rule already captured part of the temporal win for +1.4 correct, and the
change forces re-extraction of every cache (~10 GPU-h) plus a new probe
suite. Revisit after U1–U2, or immediately if round 5 shows Dynamic Update
regressing on the official split.

---

## U5 — Extended meta-memory *(blocked on data, not design)*

Entry 140 shipped the first slice: corrections induce write policy. Extending
the same machinery to abstention rules, slotting rules and gist-induction
rules is natural — but 17 corrections is not enough signal to induce more
rule families without overfitting. **Unblocks when the correction corpus
grows**, which is a dogfooding milestone, not an engineering one.

---

## Declined, with reasons

| Proposal | Why not |
|---|---|
| Evidence-graph rewrite (receipts as graph nodes) | We already have a receipted graph; entry 100 measured graph-anchored *selection* as null. No measured hook. |
| Per-attribute trust profiles | 1,227 training rows total; slicing per attribute class invites overfitting the dial we just calibrated. |
| Cross-attribute contradiction rules | Already shipped as `conflicts()` — 23 live on the owner profile, surfaced over MCP. |
| Temporal conflict rules | Substantially shipped: `timeline.py` supersession chains + the as-of rule. Refinement folds into U4. |
| Fractal / topological / thermodynamic / category-theoretic memory | No hook in the measured failure profile; the source table lists validation as early. |
| Stigmergic ingestion (repos, file traces) | Genuinely interesting, but a product *scope* decision — what to ingest — not an algorithm. Needs a product call first. |

---

## Product track (parallel, no GPU contention)

1. Wire the validated engine into the MCP surface: `profile_context` serves
   the measured config plus its calibration snippet; `trust=` selects a dial
   point.
2. Package: `uvx sourcedrecall` / `claude mcp add`.
3. Demo: the clarification loop on real data — an agent that asks "which of
   these three employers is current?" is immediately legible in a way no
   accuracy number is.
