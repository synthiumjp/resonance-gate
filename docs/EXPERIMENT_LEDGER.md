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
| Emit-once improves extraction precision | F1 25.74 → 26.77, ratio 1.68× → 1.51×, **null 0.00%** (e188) | solid, shipped `RG_EMIT_ONCE` |
| Extraction was capped by scope, not quality | best single **user** turn covers 35.4% of gold; we measured **36.12%** — at the ceiling. Any-role ceiling **86.9%**; MOSAIC reports 86.77 (e189) | solid |
| Gold is schema-shaped at the category level | 64.4% of gold falls inside a **general** 20-slot persona schema whose slots were not read off gold (e192) | solid |
| Relations must be read, not assumed | grammatical binding gives 98.9% vs a 64.9% majority-class null, n=94; survives ablating HaluMem's own template phrasing (e203) | solid |
| The late-session collapse is granularity, not extraction | single-turn ceiling FLAT across position, emissions flat, 10/10 users; half of late misses present in their own session's emissions vs a ~2-3% matched null. **Replicated on a second judged run with the current renderer** — 15.5%/50.9%/1.8% vs 15.1%/50.0%/3.3% — so it is not an artifact of the old `slot: value` syntax (e206, e208) | solid |
| Judge choice is worth ~10 points | frontier judge scores us 9.67pt lower; ~2.7pt of it is reasoning mode alone (e176/e177) | solid |

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

## 6. Open, in priority order

| # | Item | Status |
|---|---|---|
| S0 | blunt all-turns arm | **done** — +14.01pt recall, precision flat (e194) |
| S2 | refined `SYSTEM_ASSISTANT` arm | **done — NEGATIVE**, blunt path now default (e197) |
| S3 | schema `gaps()` → targeted second look | **done** — 8/8 slots, precision 50%→100% after guards (e193/e195) |
| S4 | narrative linking at write time | **closed — negative** at every budget (e198) |
| S3c | relation typing in gap probe | **done** — 64.9% → 98.9% vs gold, 0 wrong (e203) |
| S5 | **judged** A/B of all-turns ingestion | **paused** at GPU handover — base arm complete, all-turns 1/7 chunks, ~3h to resume (e205) |
| S6 | proposition rendering | **already shipped** as e163 (`590529e`, 2026-08-05) — I proposed it not having checked the artifact's provenance (e208) |
| S7 | record **bundling** — several attributes per proposition, not one | open, and distinct from S6: rendering changed each record's syntax, not how many propositions it carries. Indicative price **+4.3pt** over its own record count (e207), measured on the old format only |
| P1 | job DUTIES filed as job titles | open — clutters role history; needs a duty/responsibility slot |
| P2 | 88% of the store is `provisional` | open, **design decision not a bug**: promotion needs 2 mentions, people state most self-facts once. Either drop the rule for first-person attributes or stop surfacing tier as confidence |
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
