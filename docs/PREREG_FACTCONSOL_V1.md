# Pre-registration: updated facts v1 (approved by JP 2026-10-25)

Approved by JP 2026-10-25 ("advance with it"). The baseline is
sourcedrecall as of commit 6ad96bb, with the bench in bench/factcons/.
Added at approval, a detail the draft left open: the native writer runs
until its folder no longer fits Qwen's 32k window; where that happens
before the last session, the session is reported and native is not scored
on that list.

## Question

When a fact is replaced by a later one, does the memory give back the
later one? The false-memory sets tested this for facts about the user; this
tests facts about other people and things, which a coding or research user
also tells their assistant.

## Data

MemoryAgentBench (Hu et al. 2025), Conflict_Resolution, FactConsolidation
sets (ai-hyz/MemoryAgentBench, revision 7ea0669, MIT). Each set is a
numbered list of facts built from MQuAKE's counterfactual edits; where two
facts conflict, the later one is the answer. 100 questions a set.
Single-hop (sh): one fact. Multi-hop (mh): a chain through an updated fact.

- Dev: sh_6k and mh_6k (455 facts, one list). Already looked at: a probe
  on 2026-10-25 read 12 sh_6k questions and the store built from them.
- Held out: sh_32k, mh_32k (2,310 facts) and sh_64k, mh_64k (about
  4,600 facts). 400 questions. Seen so far: the first question and answer
  of each set (printed when the file was listed) and the second of sh_32k
  with its two conflicting facts.
- Not used: the 262k sets (too long to feed through the native writer).

## Feeding

The same for every system: the facts in order, numbers removed, 25 facts
to a session, each session one user message dated one day after the
last. Order is carried by the dates, which every system sees.

## Systems

1. sourcedrecall: profile_ingest of each session; per question the lines
   of the block an agent receives (profile_context), as on LoCoMo.
2. plain retrieval: each fact with its date as one chunk, top 10 by the
   same embedder.
3. native memory, Qwen3-14B as writer (bench/claude_memory.py's
   instructions, after each session). Labelled unfair to it, as on the
   coding set.
4. whole list in the prompt, dated: dev and where it fits Qwen's 32k
   window only (the 6k list); reported as a ceiling, not a system.

## Reading and scoring

Reader Qwen3-14B (temperature 0), Phi-4 second where the context fits its
16k window. The prompt names the date rule: when facts conflict, the later
date holds. Scored as MemoryAgentBench does: correct when the normalised
gold answer appears in the normalised answer. No LLM judge.

## What happens with the result

- The first held-out run scores sourcedrecall as it is (commit to be
  named at approval).
- If supersession is fixed afterwards, the fix is built and tuned on dev
  only, then held out is run once more with the fix, and both runs are
  reported.
- No launch gate. Reported whatever the outcome, per set, with context
  size. If sourcedrecall is below plain retrieval, the README says so.

## Results (Qwen3-14B reader; correct of 100, mean context tokens)

Held-out run 1, sourcedrecall at 6ad96bb (as approved), 2026-10-26:

| set | sourcedrecall | plain retrieval |
|---|---|---|
| sh_32k | 49 (2,206) | 89 (166) |
| sh_64k | 40 (2,260) | 94 (165) |
| mh_32k | 2 (2,559) | 8 (171) |
| mh_64k | 7 (2,294) | 10 (168) |

Whole list: too long for the 32k window on every held-out set.

The fix, built and tuned on dev only (the 6k lists; HANDOVER_PRODUCT.md
2026-10-26 evening): long messages quoted by their best sentences, values
that share only slot words kept apart, later facts in the same sentence
frame linked as "may have changed", and the note names the later fact and
its date. Dev sh / mh: Qwen 35 / 4 -> 87 / 13, Phi-4 56 / 7 -> 96 / 16
(plain retrieval 84 / 11 and 88 / 14). On by default from 8d14d39.

Held-out run 2, sourcedrecall at 8d14d39, same stored memories (the fix is
on the read side), 2026-10-27:

| set | sourcedrecall | plain retrieval |
|---|---|---|
| sh_32k | 84 (884) | 89 (166) |
| sh_64k | 80 (949) | 94 (165) |
| mh_32k | 10 (1,151) | 8 (171) |
| mh_64k | 7 (1,501) | 10 (168) |

sourcedrecall is still below plain retrieval on three of the four sets,
with five to nine times the context. With Phi-4 reading, run 2 is within
4 to 5 points of plain retrieval on simple questions and level on
two-step ones.

Native memory (Qwen3-14B writer, Qwen reader; labelled unfair to it), on
run 1's timeline: sh_32k 19, sh_64k 14, mh_32k 1, mh_64k 1, its folder
~28,600 tokens.

Phi-4 second reader (contexts that fit 16k; native memory does not):

| set | run 1 | run 2 | plain retrieval |
|---|---|---|---|
| sh_32k | 68 | 85 | 89 |
| sh_64k | 62 | 82 | 87 |
| mh_32k | 4 | 8 | 7 |
| mh_64k | 7 | 6 | 7 |
