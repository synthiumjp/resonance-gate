# Pre-registration: updated facts v1 (draft for JP, 2026-10-25)

Not approved yet. Nothing held out is scored until JP approves.

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
