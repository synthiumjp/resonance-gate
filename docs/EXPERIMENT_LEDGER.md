# RG experiment ledger

Every lever tried, what it did, and whether it survived a control. Failures and
corrections are recorded at the same weight as wins — the point of this file is
that a future reader can tell which of our beliefs are load-bearing and which
were retracted. Notebook entry numbers are the primary record; this is the index.

Standing rule behind most of the entries below: **a containment metric needs a
null**. Entries 151–153 retracted three findings that were token soup passing a
containment test. Every result here states its control.

---

## 1. What is actually established

| Claim | Evidence | Status |
|---|---|---|
| Abstentions are evidence-calibrated | median gold-overlap **0.00** when abstaining vs **0.75** when answering; same metric, same format both sides (e183) | solid |
| Inference-question gating dominates its null | beats matched-coverage random by ~2x (0.70:1 vs 0.34:1 null on round5); detector AUROC 0.933 held-out (e179/e180) | **true but re-scoped (e210)** — it picks better than random which questions to decline, and is STILL net-negative: 115 correct lost to remove 81 hallucinations, p=0.018. A trust DIAL, not a win. Do not enable by default |
| ~~All-turns gives +14.01pt extraction recall~~ | **RE-SCOPED (e212)**: proxy said +14.01pt, judge says **+1.65pt, p=0.40, null**. The proxy overstated ~8x. §5a's "paired conclusions survive" was too generous — the sign survived, the magnitude did not |
| Emit-once improves extraction precision | F1 25.74 → 26.77, ratio 1.68× → 1.51×, **null 0.00%** (e188) | solid, shipped `RG_EMIT_ONCE` |
| Extraction was capped by scope, not quality | best single **user** turn covers 35.4% of gold; we measured **36.12%** — at the ceiling. Any-role ceiling **86.9%**; MOSAIC reports 86.77 (e189) | solid |
| All-turns ingestion converts abstentions into answers | judged A/B: omission −9.49pt (p=0.007), correct +6.57pt (p=0.049, marginal), hallucination ns; 1.43 correct per hallucination on recovered omissions; precision FLAT at 57% more emissions (e212) | solid on omission, marginal on correct |
| Gold is schema-shaped at the category level | 64.4% of gold falls inside a **general** 20-slot persona schema whose slots were not read off gold (e192) | solid — **but CATEGORY only.** Gold's TEXT is prose: just **4%** (24/671) is attribute-shaped, and 428 of 452 Persona points are sentences. A typed-slot extractor optimises for 4% of the benchmark (e217) |
| **Grammar beats an LLM at extraction, decisively** | judged, **corrected sampler, TWO held-out users** (e233/e237). u0: parser **F1 0.5589** (P 0.7099 / R 0.4609) vs prompted **0.3221** (P 0.6684 / R 0.2122), +23.68pt, McNemar **p=4.8e-23**. u1: parser **F1 0.4895** (P 0.6813 / R 0.3820) vs prompted **0.2861** (P 0.6529 / R 0.1832), +20.34pt, McNemar **p=1.1e-21**. Pooled recall 0.4192 vs 0.1969. Zero model calls at extraction | **replicated on two users.** u1 is the harder user — BOTH arms fall — but the margin and the ordering hold on all four measured quantities. **Do NOT compare to the published table**: our judge is local and scores us ~9.67pt lenient (e176/e216) |
| ~~F1 0.5891 (P 0.9301 / R 0.4311), above Mem0/Mem0-Graph/Supermemory~~ | **WITHDRAWN (e233)**: `--limit-accuracy` took the FIRST N records, biasing toward early templated sessions. Every precision figure in the four rows below is head-sampled and therefore inflated — on the one arm measured both ways the bias was **+10.75pt** (prompted 0.7759 biased → 0.6684 corrected). The recalls are unaffected (integrity judges all gold points); only the precisions and F1s fall (e231) |
| ~~Grammar beats an LLM at extraction, decisively~~ | judged, held-out user 0: parser **F1 0.5435** (P 0.9524 **head-sampled, inflated** / R 0.3802) vs prompted 14B **0.3328**; recall +16.84pt at **p=1.6e-12**. Zero model calls. From second-worst on the published table to ~3pt off Mem0 (e227, e228) | recall stands; **F1 withdrawn (e233)** |
| ~~Grammar beats an LLM at extraction, decisively~~ | judged, held-out user 0: parser all-turns **F1 0.5036** (P 0.9412 **head-sampled, inflated** / R 0.3438) vs prompted 14B **0.3328**; recall +13.19pt at **p=3.5e-08**. Zero model calls. Puts us from second-worst on the published table to within 7pt of Mem0 (e227) | recall stands; **F1 withdrawn (e233)** |
| ~~Grammar beats an LLM at extraction~~ | judged, held-out user 0, same run: parser **F1 0.3611** (P 0.8065 **head-sampled, inflated** / R 0.2326) vs prompted 14B **0.3322** (P 0.7701 / R 0.2118), and vs LoRA 1.7B R 0.1701. **Zero model calls.** Recall lead not significant (p=0.34); the solid claim is that a zero-model extractor is not worse (e225) | recall stands; **F1 withdrawn (e233)** |
| ~~A specialised 1.7B extractor beats a prompted 14B~~ | **RETRACTED (e223)**: the judge says 17.01% vs 21.18%. The screen was structurally biased — token overlap over-reads GENERATED gold-shaped text by 5.4pt and UNDER-reads extractive text by 3.5pt (e225) |
| Relations must be read, not assumed | grammatical binding gives 98.9% vs a 64.9% majority-class null, n=94; survives ablating HaluMem's own template phrasing (e203) | solid |
| The late-session collapse is granularity, not extraction | single-turn ceiling FLAT across position, emissions flat, 10/10 users; half of late misses present in their own session's emissions vs a ~2-3% matched null. **Replicated on a second judged run with the current renderer** — 15.5%/50.9%/1.8% vs 15.1%/50.0%/3.3% — so it is not an artifact of the old `slot: value` syntax (e206, e208) | solid |
| Judge choice is worth ~10 points | frontier judge scores us 9.67pt lower; ~2.7pt of it is reasoning mode alone (e176/e177) | solid **about our own scores** — it does NOT license a one-sided correction against other systems' published numbers, which is how e211 misused it (e216) |

## 2. What failed

| Lever | Result | Why it matters |
|---|---|---|
| Rerank cutoff `top_n=20` | **null** (Correct net −3, p=0.72) despite halving context | the composer tolerates distractors better than missing evidence |
| Propositions in QA context | **null** (net +4, p=0.618) | rendering helps the *artifact* (judged vs prose gold), not the composer |
| Typed schema V6 as a precision filter | **null** (V6/V5 = 1.06) | see §3 — wrong class of instruction |
| Corroboration-only emission | 0.22×, a 0.37× **under**-extraction | 77.9% of stored items are single-mention; corroboration ≠ gold-worthiness |
| Provenance tiering for assistant facts | rejected before building | assistant-sourced gold is often stated once, so requiring corroboration discards it |
| Abstained-items probe | **moot, not null** | no positive class exists — nothing is withheld because nothing was retrieved |
| Bespoke `SYSTEM_ASSISTANT` prompt | **negative** — recall 35.77 vs blunt 52.01, precision 16.08 vs 22.96 | the elaborate solution lost to reusing the prompt we already had (e197) |
| Narrative linking / 1-hop expansion | **closed** — flat at every budget | only 21.2% of question gold is in the store; retrieval already gets 71% of it (e198) |

Reported as *moot* rather than *null* deliberately: we did not run an
underpowered probe and present its failure as a finding.

## 3. Laws, and one correction to them

- **Assertion calibration cannot be prompted.** Ten interventions telling the
  model how confident to be have failed, converting omission→hallucination ~1:1.
- **Scope rules CAN be prompted.** "Ignore roleplay", "ignore code paths",
  "do not extract advice" all hold.
- **The distinction** is whether a rule names *what counts* or *how much to
  hedge*. V6 failed because "emitting fewer is correct" is calibration wearing a
  schema's clothing (e186 → corrected in e191). I over-generalised the law in
  e186 and it would have ruled out the `SYSTEM_ASSISTANT` fix that followed.
- **Mechanism for the law**: JP's "Represented but Not Expressed" — an
  output-stage override leaves the internal representation intact, so no
  recalibration of the emitted distribution recovers what the model still holds.

## 4. Instrument failures — the most repeated mistake

Four times in one session a measurement was wrong because we trusted what it
was *called* instead of reading what it *computed*:

1. `search_duration_ms` includes the composer LLM call → "retrieval costs 4.5s"
   was wrong; it is **~156 ms** (e180 → e181).
2. A scratchpad `profile.py` shadowed the stdlib module `cProfile` imports,
   silently breaking an unrelated run.
3. Duplicate-emission count run over raw strings missed every promotion,
   because `_fact_str` appends the tier — 0.6% → **10.1%** (e187).
4. Lexical slot census said gold was not schema-shaped (40%); category-level
   mapping says **64.4%** (e192).
5. `slot_filled` matched cues anywhere in a 983-fact store and reported 22/23
   slots filled — it could not return a negative. Attribute-name matching gives
   15/23 (e193). *Caught before publishing.*
6. Store-vs-gold coverage measured against **raw atoms** instead of rendered
   propositions → "65pt of headroom" was wrong; it is **21.2pt**, and we are at
   75% of ceiling not 25% (e199 → **retracted in e200**).
7. The overlap threshold sits on the distribution mode — see §5a (e202). Not a
   bug: a **limit**. The instrument works and is not precise enough.
11. `merge_probe` reads its grouping key off the `slot:` prefix, which
   proposition rendering removed. Every record then parses as slot `""` and
   by_slot degenerates to `all` — 61 records for 1014 emissions, printed as a
   3x win (e208). It now asserts the format. **A probe that parses a rendered
   string is coupled to the renderer and will not fail loudly on its own.**
12. Position-based cuts read chunk-local session indices on chunked runs
   (`<uuid>#c3` restarts at session 0), silently scoring session 31 as
   session 4 (e208).
10. A merge strategy scored +9.9pt on gold coverage — but merging makes each
   record a bigger token set, so it covers more of ANY gold. Randomly merging
   to the same record count scored +5.6pt of that. Real effect **+4.3pt**
   (e207). Same shape as e151–153: containment without a null. *Caught before
   it reached this table as a finding.*
8. `re.I` applied to a whole pattern also lowercases `[A-Z]`, so a gold parser
   read `"'s friend invited her"` as the person **`invited`** — 26 of 120
   "relationships" were verbs (e203). Scope the flag: `(?i:(friend|...))\s+([A-Z]\w+)`.
   First one inside a measurement written in the same session it was used;
   caught only because the miss list was printed.
9. `s5_compare` pooled each A/B arm over whatever chunks it had judged. With a
   partial run (base 7 chunks, all-turns 1) that compares different session
   ranges, and by e204 the LESS FINISHED arm wins by construction — it printed
   all-turns +10pt on precision; like-for-like, base is ahead by 3pt (e205).
   **A resumable run's resting state is unequal arms, so any comparison over
   one needs a completeness guard, not just a correctness one.**

**Third clause, added after #11/#12: read the ARTIFACT'S PROVENANCE, not just
its contents.** Entries 206/207 diagnosed a rendering format we had already
replaced two days before the run was generated. Any conclusion from
`rgp2-round5` carries "pre-590529e format" as a condition.

13. `w1_update_ab` read `result_type` off the update judge, which returns
   `evaluation_result` (`evaluation.py:170`) — `result_type` is the QA judge's
   key. Every record scored None and the run exited 0 (e213). **An all-None
   result with a clean exit code is indistinguishable from "no effect" unless
   the script asserts its scores are in the harness's own valid set.**

**Standing rule: before drawing a conclusion from a metric, read its
assignment.** This has cost more than any modelling error. **Second clause,
added after #6: when comparing our store to gold, render it the way we would
report it.** Comparing internal representation against external gold is the
specific trap, and it has caught us twice on the same axis (e162, e199).

## 5. Where the headroom is

Not composer-side. Entry 183 localises omissions to retrieval/extraction, and
context **size** (e178) and **form** (e184) both measured null — so every
composer-side lever is bounded by what retrieval hands over.

Not aggregate accuracy either. HaluMem is two tasks with a 53-point spread:
retrieval categories **64.1%** correct / 15.0% hallucination, inference
categories **11.2%** / 46.2% (e179). Reporting the mean hid the only part of the
system that is good.

## 4b. Prompt engineering: 0 for 3 this session

V6 typed schema (null), `SYSTEM_ASSISTANT` (negative), and "if unsure output []"
in the gap probe (needed deterministic guards instead). **Every extraction win
came from scope of input (all-turns) or deterministic post-processing**
(emit-once, self-reference guard, multi-value splitting). Treat that as a design
rule, not an observation.

## 5a. The offline proxy is exhausted for absolute questions

The token-overlap containment metric uses a 0.5 threshold that sits **exactly on
the mode** of the gold-vs-store overlap distribution. Coverage reads ~85% at
0.4, 64.8% at 0.5, ~28% at 0.6 (e202). Its sensitivity to an arbitrary constant
exceeds the effect size we are chasing.

- **Absolute figures from it are unreliable** — e200's 64.8% and e201's 21.2pt
  are wide bands, not numbers.
- **Paired A/B conclusions stand** — a threshold shift moves both arms together,
  so S0 (+14.01pt), emit-once, the linking null, the S2 negative and the top_n
  null all survive.

Further extraction work needs the judged harness (~5,500 calls/arm), spent on
one well-chosen change rather than on exploration.

## 5d. No instrument in the stack reads the text

Three product defects shipped for months and nothing could see them: 7% of
records were broken English, changing attributes never superseded (18 answers
to "what do you do?"), and groups carried personal attributes ("Ai works as
empathetic interaction"). The proxies compare token SETS (near-invariant to
grammar); the judge's per-record score tracks GOLD MEMBERSHIP (in-gold mean
1.330 vs out-of-gold 0.022, no in-gold record scores 0); every aggregate is a
mean over one of those. **`store_view.py lint` is now the check that reads the
text, and it runs before judge spend.** If a defect would be obvious to a
person reading the output, it belongs in lint, not in a metric (e209).

## 5c. The judge credits RECORDS, not stores

What separates credited gold from missed gold is not whether we hold the
content — it is whether ONE of our records covers it alone. Late misses have
50% union coverage of their own session's emissions but only 15.1%
single-record coverage; credited gold runs 88.5% / 57.8% (e206). Our records
are short `slot: value` facts of constant granularity, and late gold bundles
several propositions per sentence. **Store-level coverage is the wrong target;
record-level coverage is the metric that pays.**

## 5b. Retrieval is near its ceiling — stop tuning it

Of 179 gold points the questions need, **24 (13.4%) are in the store at all**,
and retrieval already surfaces ~10% — about **75% of what is available**
(e196; all-turns store: 21.2% present, ~71% of it retrieved, e198). Retrieval
tuning therefore has only a few points of headroom on this store, which
retrospectively explains `top_n` (e178) and propositions-in-QA (e184) being
null. Those were not bad ideas badly executed; there was no room.

## 5i. Shape beats knowledge on this benchmark

Five judged A/Bs on the update axis. Four architectural fixes — report
supersession, double the prior-fact coverage, alias the state slots, add the
reverse link — all NULL, though each fixed a real defect. The fifth, rendering
the same facts as subject-bearing propositions, moved it 3.7x (e215).

**The judge credits RECORDS, and a record has to be the right shape** — now
measured on integrity (e206), replicated under a different renderer (e208),
and confirmed on the update axis (e215). On this benchmark how we SAY a thing
has repeatedly mattered more than whether we know it. Both matter for a
product; only one was being worked on.

## 5h. The extractor supersedes in the attribute NAME

`employer`, `current_employer`, `former_employer`, `past_employer` and
`previous_employer` all exist in one user's store. The extractor already knows
a fact has been replaced — and encodes it as a NEW SLOT rather than a new
value, three different ways, guaranteeing old and new never meet. No conflict
is detectable and both stay current forever. 161 attribute names for one user;
gold wants ~20 (e192, e214).

## 5g. Architectural reasoning is not evidence of a lever

Twice in two days a TRUE statement was read as a different one:
  * "the gate dominates its null" -> "so turn it on to cut hallucination"
    (e210: it is net-negative, 0.70:1)
  * "every leader supersedes at write time" -> "so it will move our updating
    score" (e213: null, because the axis is omission-bound at 92%)

**Before building a mechanism, measure whether the axis it targets is bound by
what it fixes.** Both checks cost nothing — the records were already on disk.

## 5f. Two mechanisms, one axis, opposite directions

Measured in the same run, on the same trade:

    RG_QGATE     correct -> omission    0.70 : 1   UNFAVOURABLE (e210)
    all-turns    omission -> correct    1.43 : 1   favourable   (e212)

**Declining to answer loses more than it saves; handing the composer more
evidence gains more than it costs.** §4b's law on the QA axis, now measured
from both ends. Both are DIALS for the user's loss function, not defaults.

## 5e. Where we actually sit (e211, CORRECTED in e216)

Unadjusted, same benchmark, same split:

    QA correctness    RG 52.6 (official row) / 55.0 (round5)
                      Mem0 53.02  Mem0-Graph 54.66  Supermemory 54.07
                      Zep 55.47   MemOS 67.23   MOSAIC 73.10
    extraction F1     RG 28.2 / 38.3 | Memobase 25.13, Mem0 57.31,
                      MemOS 79.70, MOSAIC 86.77
    updating          RG 2.9 -> 8.1 (e215) | Memobase 5.20, Mem0 25.50,
                      Zep 47.28, MemOS 62.11

**PRODUCT NOTE (e258): these are BENCHMARK numbers and the product read path
was not running the benchmark's retriever.** `profile_recall` shipped token
overlap while retrieval v3 ran only on the QA path; on a dogfood store that is
5/10 vs 7/10 rank-1 and 5/10 vs 9/10 in top-3. Nothing in §5e measures what a
user experiences.

**On QA we are MID-PACK — level with Mem0 and Zep, behind only the two
leaders.** Entry 117 said so in July. e211 wrongly applied e176's −9.67pt
frontier-judge penalty to OUR number alone to claim "~45–47, below the pack";
a stricter judge penalises everyone, and the published table's judge is
unverified (HaluMem reads it from `OPENAI_MODEL`). **That figure is
retracted.**

**The real gaps are extraction (20–50pt) and updating (17–54pt)**, and those
survive the judge objection by size — a ~10pt scorer effect cannot explain
them.

Note what this combination means: we answer as well as Mem0 while extracting
about half as well. Retrieval/composition are doing more with less (cf. §5b,
~75% of what the store makes available) — and the extraction gap is invisible
on the axis where we look fine, which is why it went unnoticed.

Competitors in our niche as of 2026: **AgentPrizm** (July 2026, hosted:
confidence-weighted facts, receipts, supersede chain, verifiable deletion),
**Eywa** (arXiv:2605.30771 — evidence-before-belief, tunable abstention,
**refusal-aware F1**, published traces), **MOSS** (arXiv:2607.04391 — same
philosophy, zero benchmarks). The unoccupied intersection is local + small
model + receipts + measured abstention. **Local is the wedge; receipts are the
mechanism, not the headline.**

## 5l. Token overlap cannot see a negation

Four correctness bugs shipped invisibly to every instrument: dropped negation
("I don't like boxing" stored as "does like boxing"), an absorbed comma splice,
a contiguous slice of a discontiguous subtree, and relationships built from any
noun. An inverted sentence shares every content token with the true one, so
coverage scores them the same; a duplicated span scores HIGHER (e228).

They surfaced only from READING judged misses and raw output. **A store that
ships the negation of a fact is worse than a store that ships nothing**, and no
overlap metric will tell you which you have.

## 5k. Over-emission does not cost precision — and pruning does not buy recall

`target_accuracy` scores each record ALONE, so surplus cannot dilute it (e224).

**Sharpened (e235): this is DEFINITIONAL, not empirical.** The harness computes
`prec = k/n` where `n` counts only records with
`is_included_in_golden_memories == true`. An out-of-gold record is dropped from
BOTH numerator and denominator, so it cannot move precision by any amount. The
consequence is the uncomfortable one: **the benchmark cannot penalise a wrong
record at all** — only a wrong record that gold happens to contain. ~12% of our
records are assistant QUESTIONS asserted as facts ("Martin Mark does have What
kind of personality"); the metric's incentive is to leave them in, because
removing them can only risk recall. Product defect, benchmark-invisible.

e229 saw +28 records cost 1.2pt of recall and proposed that the integrity
judge's concatenated blob crowds out matches. **That mechanism is RETRACTED
(e230):** capping to 25 records/session cut 67% of records and cost **12.15pt**
of recall (38.02% → 25.87%). If crowding were real, pruning would have helped.
Records earn their place; e229's small regression is unexplained and most
simply read as judge variance.

`grammar_check.quality()` (grounding + brevity + shape, no model) is kept — not
as an F1 lever, which is measured harmful, but as the ordering a PRODUCT needs
for what to show first and what to surface under a context budget.

## 5k-corr. Over-emission — the e229 correction

**Corrected in e229.** `target_accuracy` scores each record ALONE, so surplus
cannot dilute it — the original finding holds for the term it named. But
`integrity` hands the judge a session's emissions as ONE CONCATENATED BLOB and
asks whether a gold point is in it, so surplus is a longer haystack. Adding 28
gold-shaped records took judged recall 38.02% → 36.81%, moving 9 gold points
from credited to missed.

So: do not read this as a licence to emit freely. The parser's 4834 records may
already be costing recall — a live hypothesis with a cheap test (prune to the
best records, see if recall rises). If it does, a checker layer earns its place
as a RECALL filter, which is the opposite of the job it is usually given.

## 5k-orig. Over-emission does not cost extraction F1

`evaluation.py:289` computes `memory_extraction_f1` from `target_accuracy(all)`,
and that term is summed **only over records the judge marks
`is_included_in_golden_memories`** — 46% of emissions on s5-base, 41% on
round5. Records not about gold content are excluded, so emitting them costs
nothing on F1 (e224).

**Entry 185's "we emit 1.66x more memories than gold" has been read as a
precision problem since. On the metric the harness reports, it is not one.** It
may still be a product problem — surplus is worse to use and worse to retrieve
from — but that argument should stop being made in F1's name.

Consequence: a checker layer should FIX the in-gold records, not FILTER the
surplus. And entailment filtering cannot do the job regardless — a true
proposition absent from gold is still entailed by its turn, so entailment
measures groundedness, not gold-worthiness.

## 5j. The composition line, closed

Relationship composition is real (+10.8pt over atoms on Relationship gold,
+8.1pt over its null, for 14 records) and confined to 7% of gold. Persona
+0.3pt and Event +0.0pt, both fully matched by the null. **Pooled +0.6pt**
(e220). Recall 0.290 -> 0.296. Closed.

Banked and kept: `person_subject` (10/10 leaks vs baseline 3/10, 0 false
rejections) and `entity_resolve` (0 wrong merges, null 0%) — both product
fixes independent of the shelved composer.

**Proxy calibration, measured:** offline coverage reads 46.3% of non-update
gold where the JUDGE scores integrity recall 27.8% on the same store — the
proxy over-reads by ~18pt. Never quote an offline coverage figure as "recall".

## 5m. The benchmark cannot see a defect the product trips over (e258-e260)

`"It's in Go, which I didn't know before I joined"` rendered as `<owner> did
not know which`. That defect is **4 of 6661 records on u0 (0.06%)** and **2 of
14 nodes in a real dogfood store (14%)**, where it ranked FIRST for nearly
every unanswerable question. HaluMem's synthetic prose barely uses relative
clauses; conversation does.

Three consequences, all measured:

1. **Dogfooding found in one session what nine entries of benchmark
   decomposition did not.** e258 (the product read path never got retrieval
   v3) and e259 (the relative pronoun) both came from USING the thing.
2. **A render defect corrupted an evidence signal three layers away.** With
   the garbage node gone the cross-encoder's score separates answerable from
   never-mentioned cleanly, 18/18; before it, the populations overlapped.
   Nothing about the retriever changed.
3. **A validated component reaching only one path is now a THIRD confirmed
   instance** (e248 renderer, e251 stale run copy, e258 retrieval). Assume it
   for anything validated on the benchmark path until checked.

## 5n. Owner-token prefixes compress the scores a floor depends on

`RG_INDEX_TEXT` -- indexing the full proposition instead of `attr: value` --
is null on rank-1 and pool AND destroys the abstention separation (known-min
-9.28 falls below unseen-max -8.22, e260). Every proposition begins with the
owner's name, so a constant prefix flattens exactly the differences the floor
reads. e256 hit the same artifact from a different direction (97.6% of
name-shaped mentions are the owner). **Measured twice, under different
upstream conditions. Closed.**

## 5o. An absolute score threshold degrades as the store grows (e274)

The v3 abstention floor separated answerable from never-mentioned questions
**cleanly, 18/18, at 14 store nodes**. At 38 nodes nothing separates them
cleanly and the best absolute cutoff costs one false answer in seven --
max-of-N rises with N. Two margin variants are worse at both sizes.

**Any constant fitted on a small store is a property of that store.** The fix
is not a better constant but a SECOND independent signal: grounding (lexical
or dense) does not degrade with size, and is ANDed with the floor. A real
store has thousands of nodes; e260's confidence in the clean split was
misplaced and is corrected here.

## 5p. A probe names a FACT, and facts change (e275)

Five "system failures" chased this session were stale probes: the car (e268),
the vegetarian (e273), the dog, the employer, and "Where do I work?" -- which
was called an unfixable semantic limit for six entries while the store
answered it correctly. Every corpus extension can invalidate a needle.

`tools/dogfood.py:check_probes()` is the structural guard: a recall needle may
not name a value CURRENCY lists as superseded, and an UNSEEN question may not
name something the corpus discusses. It runs before every scorecard.

This is §4 again, committed five times in one session **after** writing the
warning down twice. The lesson that generalises: an instrument built to
localise a problem must be re-validated every time the system under it
changes, and "my measurement says X" is a claim about the measurement first.

## 5q. A measurement axis cannot find what you did not think to test (e276/e277)

Six axes -- recall, abstention, PURITY, tiering, currency, conflict -- read
**21/21 purity and 9/9 abstention** while SEVEN false-fact classes were live,
two of them straight polarity inversions ("WilsonRobert is not a fan of jazz"
stored as "IS a fan"). Ninety minutes of adversarial review by four reviewers
found more than a full day of building those axes.

The axes are not worthless -- they caught e258, e259, e273 and are now
regression guards. But they encode what I ALREADY suspected. **Budget
adversarial review as a recurring activity, not a one-off audit at the end.**

Two corollaries, both earned the same evening:
- **The strongest safety net was an OLD entry's tests.** Wiring the hearsay
  tier into `recall_v3` instantly re-introduced e250's defect (hearsay
  appended to unrelated questions); e250's tests caught it in minutes.
- **A reviewer's finding is not automatically a defect.** One "indirect
  question" fix broke five tests asserting e235/e237's deliberate design. One
  adversarial example does not outrank tested intent.

## 5r. A validated fix behind a flag nobody sets has not shipped (e277)

e258 concluded "the product never got the retriever we validated" and then
shipped v3 behind `RG_PROFILE_V3=1` -- set by no server startup path, no
README, no install instruction. **e258's own conclusion was therefore still
true after e258.** Same shape: `RG_HEARSAY` built an index `recall_v3` never
read, so the flag was inert exactly where it mattered and worked on the
benchmark.

FIFTH and SIXTH instances of 5m. The rule to apply: after wiring a capability,
**check what the DEFAULT does**, and check it from the surface a user actually
calls -- not from the test that sets the flag.

## 6. Open, in priority order

| # | Item | Status |
|---|---|---|
| S0 | blunt all-turns arm | **done** — +14.01pt proxy, judged NULL +1.65pt (e212). But worth **+11pt to the PARSER** once it could read the second person (e227): scope was never the lever, reading it was |
| S2 | refined `SYSTEM_ASSISTANT` arm | **done — NEGATIVE**, blunt path now default (e197) |
| S3 | schema `gaps()` → targeted second look | **done** — 8/8 slots, precision 50%→100% after guards (e193/e195) |
| S4 | narrative linking at write time | **closed — negative** at every budget (e198) |
| S3c | relation typing in gap probe | **done** — 64.9% → 98.9% vs gold, 0 wrong (e203) |
| S5 | **judged** A/B of all-turns ingestion | **DONE (e212)** — recall null (+1.65pt p=0.40), omissions −9.49pt (p=0.007), precision flat at +57% volume. Ship as a trust DIAL, not a default |
| S6 | proposition rendering | **already shipped** as e163 (`590529e`, 2026-08-05) — I proposed it not having checked the artifact's provenance (e208) |
| S7 | record **bundling** — several attributes per proposition, not one | open, and distinct from S6: rendering changed each record's syntax, not how many propositions it carries. Indicative price **+4.3pt** over its own record count (e207), measured on the old format only |
| W1 | move supersession from READ time into the WRITE path | **DONE, and NULL on the metric (e213)**: 0.7% → 2.2%, p=0.5. Kept — it is correct, cheap and the product behaviour depends on it — but the update axis is omission-bound at 92%, not supersession-bound. Only **25%** of update-relevant facts are in the store at all; retrieval surfaces 13% |
| W1b | extract the PRIOR value of an updated fact | **mechanism confirmed, lever NULL (e214)** — all-turns doubles prior-fact coverage (25%→44%) and retrieval (13%→27%); updating accuracy unmoved at 2.2%, p=1 |
| W1c | retrieval for update queries | **cleared as the cause (e214)** — we retrieve the right facts and the judge still sees no update |
| W2a-e | **render the update readout as propositions** | **DONE, the only thing that moved it (e215)**: updating **2.2% → 8.1%**, omissions −11.1pt p=0.0003. `search_memories` never got e163's renderer and was emitting `attr: value` into the one place gold is most sentence-like |
| **W2a** | **attribute canonicalisation** | **THE LEVER (e214)**. One user's store: **161 distinct attribute names**, 14 for health, 5 for employer including `former_/past_/previous_employer` — the extractor superseding in the SLOT NAME, so keys never collide and W1 fires on 22 of 1270 nodes. Gold wants ~20 (e192). Deterministic post-processing; should move updating, extraction F1, the contradictory-store defect and retrieval at once |
| W2 | adopt **refusal-aware F1** (Eywa, arXiv:2605.30771) | our abstention claim is currently unfalsifiable in exactly the way that metric punishes |
| W3 | re-validate the e130 dial on held-out data | it is a hidden-state probe; two independent replications show that class collapsing to ~0.58 OOD (e211) |
| P1 | job DUTIES filed as job titles | open — clutters role history; needs a duty/responsibility slot |
| P2 | 88% of the store is `provisional` | **candidate fix identified (e221)**: PT-CSFT (JP's own, arXiv:2604.24070) trains the extractor to emit a probe-calibrated confidence per memory point, replacing a corroboration count that cannot work when people state self-facts once. Do NOT ask a small model for a 0–100 number — arXiv:2604.22215 measured all seven 3–9B models Invalid at that, 91.7% ceiling |
| W3 | re-validate the e130 dial | **instrument identified (e221)**: JP's Validity Scaling Protocol (arXiv:2604.17707/.17714/.17716) — Invalid models score AUROC ~0.36 on selective prediction while APPEARING well-calibrated, which is precisely the risk |
| X1 | specialised extractor (LoRA) | **adapter-v3 BEATS the prompted 14B on held-out users (e222)** — coverage +1.3/+4.6/+7.4pt at thr 0.4/0.5/0.6 with **3.9x fewer emissions** (0.48 vs 1.86 rec/gold). Per-record hit rate 51% vs 11%. Screen passed → earns judge calls. Precision still unmeasured |
| — | judged `no-tier` run | the one audit hypothesis the proxy could not test |

S5 is what §5a called for: entry 194's +14.01pt was a proxy result, and the
proxy is exhausted for absolute questions. Paired on user 10 (the only user
with assistant turns extracted), one variable, costed offline at 1822 vs 2398
judge calls before launch. `experiments/p2/s5_run.sh`.

## 6b. Caveat on the recall numbers

`ab_artifact` reports **52.01%** recall — of SESSION memory points covered by
the emitted artifact. Only **21.2%** of the golds the QUESTIONS need are in the
store. Question-relevant golds are harder than average session golds, so
artifact recall overstates how useful the store is for answering. Do not quote
52% without this.

## 6c. Validated-then-invalidated: re-check before shipping

The eval path honours EIGHT flags; the banked official row used THREE. The
temptation when asked to compete is to turn the rest on. Do not. `RG_QGATE`
was validated at 4.65:1 in e180 and measures 0.70:1 today, because e180
predates `RG_RETRIEVE_V3` — retrieval improved, inference questions became
answerable, and the population the gate declines is no longer mostly
hallucination (e210). **Any mechanism validated before a component it sits
downstream of changed must be re-measured, and for the gate that cost nothing
because the judged records were already on disk.**

## 7. Unvalidated stack — read before any official run

Seven changes are wired but **not** individually validated end-to-end: V6 typed
schema, `SYSTEM_ASSISTANT`, all-turns ingestion, persona schema, emit-once,
no-tier, and the inference gate. Only the **gate** and **emit-once** have
survived a null test.

Running an official pass on the stack would produce a number nobody can
attribute — a null would not say which change failed, and a win would not say
which earned it. That is exactly how entries 151–153 happened. One variable per
measurement, and no official run until extraction settles, because anything
measured downstream of a moving extractor gets re-measured anyway.
