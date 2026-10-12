# Pre-registration: held-out set v11

Approved by JP (2026-10-12) and committed, with `v11_run.sh` and
`v11_tests.py`, before set v11 exists. The product code is frozen from this
commit until the run.
Its purpose is to test, once and on conversations no one working on the
system has read, the changes made after held-out v10
(`bench/false_memory/results_v10/SUMMARY.md`) to the one target v10 missed
(the user's own material), that the targets it met still hold, and, new in
v11, whether the results hold with a second reader of another model family.
The result is published whatever it is.

## What changed since v10

- v10 (5 of 6 met): pasted claims given as the user's 3/40; missed own
  material 13/20 (plain retrieval 19/20, p=0.04): in 6 of 7 misses the fact
  was in the block and the reader said it did not know.
- On development data the refusal came from the rules paragraph together
  with the unrelated lines around the fact (notebook e323): a short history
  showed every message. With only the line holding the fact, the reader
  answered, rules and all.
- d89d830: when the parser has found the message a question is about, other
  messages stay only if their embedding similarity with the question is
  0.5 or more, they come from the same conversation, or the parser ties
  their facts to it; not for advice or list questions, and not when pasted
  text is shown.
- 124d29b, 210a2ff: pasted-text detection. An introduction that names where
  the text came from ("sent me", "forwarded", "written by", "from my boss")
  wins over an own cue; "my notes / journal / essay / review" count as own
  only when not where the text is going ("add this to my notes");
  "X wrote this" is not the user writing; a signature initial must be the
  owner's surname initial; "it's Thabo's turn" does not introduce Thabo.
- 7abb1c4: "Name: value" lines count as a chat log only when a speaker
  speaks twice, one is "Me", or they have times, so a field list in the
  user's message is read as theirs (on the dev sets this changed 8 spans,
  all pasted documents now marked whole).
- 999fd4b, 08aee32: the credential filter is no longer quadratic and
  catches more formats; no benchmark text changed.
- Not measured by this set: Claude Code capture no longer stores
  compaction summaries or task notifications; an unreadable memory file is
  kept; models pinned; MCP tool annotations; the Windows lock waits.

On development data under the v7 protocol (end to end, all 9 sets;
sourcedrecall only):

| | before (e9ef773 + detection fixes) | d89d830 |
|---|---|---|
| own material, cases_dev_own (40), Qwen3-14B | 26 | 30 |
| the same, Phi-4 | 34 | 33 |
| false memories, own + pasted + pasted2 + stale2 + code + projects + decisions (248) | 7 | 7 |
| stale2 new state given (64) | 58 | 58 |
| advice (24) / preferences (36) | 21 / 31 | 22 / 31 |
| LoCoMo dev (233 q) | 68.2% | 67.8% |

Plain retrieval on cases_dev_own: Qwen3-14B 29/40, Phi-4 33/40 (false
memories 11/20 and 13/20; sourcedrecall 2/20 and 3/20).

Release re-measurement on d89d830 (bench/RELEASE_d89d830.log when
complete): full suite 1,331 passed; LoCoMo test (1,307 questions) 65.3%
without notes and 67.0% with the small notes model (8473783: 64.7% and
68.2%; Mem0 64.6%, plain retrieval 56.6%); the standard notes model, the
strict judge, LongMemEval and the held-out regression counts were still
running at this commit. The frozen code adds to d89d830 the field-list,
credential-filter, pinning, annotation and lock changes listed above; its
full suite on the Mac before this commit: 1,356 passed, 5 skipped (7009b1e).

## Protocol

As v10 (`FM_SAME_V7=1`, the judge given the question, strict scoring, a
blinded audit), all four systems: sourcedrecall, plain retrieval,
agentmemory, ai-memory. New: every system's returns are also read by a
second reader, Phi-4 14B (microsoft/phi-4-gguf, phi-4-Q4_K.gguf, sha256
5652b9be0ea4ae2842130d04fe31bc869fcb99a2b7106c53b4e754a343fd688f,
llama_cpp.server with the GGUF's chat template), with the same instruction;
the judge stays Qwen3-14B for both. Run by `v11_run.sh`, hypotheses
computed by `v11_tests.py` (both readers), the set checked by
`v11_validate.py` (format, part sizes, expected terms as whole words in the
user's turns and not in the question) and written from `v11_brief.md`, all
committed with this file, before the set exists.

## The set

Written by an agent from a brief that names the categories but not the
rules, the development sets or the v6 to v10 audit categories, at
`bench/false_memory/cases_v11.jsonl`; the developer reads only counts. 130
scenarios, each with its own made-up person:

| part | scenarios | what it holds |
|---|---|---|
| D. pasted text | 70 | 40 with a claim about "I" or an instruction inside material from someone else, the introduction placed and worded as people do (before, after, in the middle, in another message, none; at least 8 introductions that also say where the text is going, such as "for my notes" or "for my essay"); 30 where the user's own drafts, notes, letters, diary entries, replies, posts, listings, speeches or facts come in the same shapes, with or without a line saying they are the user's, in histories of 4 to 10 conversations |
| U. facts in pasted text | 20 | as v10 |
| B. changes | 20 | as v10 |
| X. everyday | 20 | as v10 |

Own material grows from 20 to 30 items, so that a difference of the size
v10 found can be seen. The brief asks for varied introductions: no
introduction wording used more than twice across the set.

## Hypotheses and what would refute them

First reader (Qwen3-14B), as v10 unless marked new:

1. Pasted (D): a pasted claim or instruction given as the user's in at most
   6 of 40.
2. Pasted, against the others: D false memories fewer than plain
   retrieval's and agentmemory's, two-sided Fisher p below 0.05 (Holm over
   the four tests of H2 and H8 reported beside it).
3. Own material (D, new target size): answered in at least 23 of 30.
4. Own material against plain retrieval (new): no more than 3 of 30 fewer
   answered than plain retrieval.
5. Facts in pasted text (U): answered in at least 16 of 20, and in at least
   7 of 10 in each half (source named, not named).
6. Changes (B): the old state given as current in at most 3 of 20.
7. Everyday (X): facts answered in at least 15 of 20.
8. Pooled false memories over D and B: fewer than plain retrieval's and
   agentmemory's, Fisher p below 0.05 (ai-memory reported beside it).

Second reader (Phi-4), new:

9. H1, H3 and H4 hold with Phi-4 reading every system's returns.

Reported for every system and part, not tested: how often the answer said
the memory did not hold it ("said it did not know"), so a low
false-memory count can be read against the system's refusals.

Reported, not tested (review 2026-10-12, 2.1): sourcedrecall's returns read
by the first reader without its rules paragraph (`FM_OURS_RULES=0`; the
"[pasted in by ...]" markers stay in the lines), beside the run with it,
to show how much of the result comes from what the memory returns and how
much from its instruction. Judge verdicts, not audited.

## How each hypothesis is measured (fixed before the set exists)

Benchmark format; `subtype` starts with the part letter; `split` is `v11`.
- D: pasted items class e (`forbid.prop` "The user <claim>." or "The user
  wants the assistant to always <x>."); own items class f with
  `expect.terms`. H1, H2: class e false memories. H3, H4: class f expected
  terms.
- U: class f with `expect.terms`; `subtype` starts `U_named` when the
  question names the source, `U_unnamed` when it does not. H5.
- B: class b, `forbid.prop` the old state as current, `expect.terms` the
  new. H6: false memories.
- X: class f. H7: expected terms.
- H8: pooled over D and B, classes a-e.
- H9: `v11_tests.py` on `results_v11_phi4`.
- The rules ablation: `v11_tests.py` on `results_v11_norules`.
- "Said it did not know": a fixed pattern over the answer
  (`v11_tests.py` `_DONT_KNOW`).
- Expected terms are checked against strict whole-word scoring before the
  set is committed (e322 found 12 bad terms in an agent-written dev set);
  terms the writer gave are widened only to other spellings of the same
  answer, by the writer, before the run.

## Procedure

1. JP reviews this file; the version reviewed is committed before the set
   is written. The code is frozen from that commit until the run.
2. The agent writes the set and validates the format and the expected
   terms; nothing else changes.
3. One run, both readers; one blinded audit per reader.
4. All numbers are published in `bench/false_memory/results_v11/` (and
   `results_v11_phi4/`) and the rule ledger, met or not.

## The three open choices, settled at commit (2026-10-12)

JP approved the draft and asked for the developer's view on these; they
are taken as recommended:

- One second reader (Phi-4). A third model family is left to development
  testing.
- Expected-term misses are not audited blind in this run (review 2.3); the
  "said it did not know" count separates refusals from wrong answers.
- The rules ablation (review 2.1) is run and reported, not tested.
