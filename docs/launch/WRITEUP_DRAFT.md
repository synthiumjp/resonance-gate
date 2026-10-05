# Memory without model calls: what a grammar parser is good for

Draft, 2026-10-04. The false-memory answers were audited (every flagged answer
read; counts in the notebook). The LoCoMo numbers are not audited.

## The question

Most agent memory systems call a language model for every message they
store: Mem0 extracts and merges facts with one, others summarise. That costs
money or local compute on every exchange, and the stored memory is the
model's paraphrase of what you said.

sourcedrecall stores nothing but what you wrote. A deterministic grammar
parser (Stanza dependency parses plus hand-written rules) reads each message,
but it does not produce the evidence the agent sees. We tried that first and
it lost. What follows is how we found out and what the parser ended up
being for.

## How we measured

What a user notices is the answer the agent gives, not the list of memory
lines behind it. So for every system we gave its retrieved memory to the
same reader model and judged the reader's answer:

- reader: Qwen3-14B (and Qwen3-4B, to see what a small local model does),
  temperature 0, run locally;
- judge: Qwen3-14B with a fixed one-question rubric ("does this answer state
  the proposition as currently true of the user?"), checked against 30
  hand-labelled items (29/30) and against an earlier judge on 198 items
  (197/198);
- systems: sourcedrecall, Mem0 2.2.1 (fully local, same LLM), and plain
  retrieval (each user message embedded with bge-small, top results with
  their dates).

Two benchmarks:

1. LoCoMo (Maharana et al., 2024): long two-person conversations with 1,307
   questions on conversations 2-9. Conversations 0-1 were our development
   set; 2-9 were run once per version we report.
2. Our false-memory set: synthetic scenarios where something about the user
   changes (a move, a new job, quitting coffee), plus controls where nothing
   changes, plus questions about things never mentioned. The blind sets
   (v2, v3, v4) were written before any system was run and the developer
   never read their text; an agent audited the judge's flags and reported
   only counts.

## What happened

Version 0.4 used the parser's facts as the evidence: each line was a
rewritten fact ("Dana Cole lives in Fitzroy") with the quote attached. Judged
line by line, it looked safer than plain retrieval. Judged by the reader's
answers, plain retrieval was better on every set: LoCoMo 56.6% against our
33.4%, and on changes of state 7/44 stale answers against our 13/44.

Reading the dev failures showed why. The answer was often in the rest of the
user's message ("...a gift from my grandma in Sweden. It stands for love,
faith and strength"), or in the reply to a question the other person asked,
neither of which a single parsed sentence carries. And readers resolve
dated original messages better than rewrites.

So 0.5 gives the reader the user's own messages, dated, oldest first, with
the question each answered. The parser stays, in four roles:

1. Routing. It finds messages through its facts, and a search over the
   messages finds others; the two take turns filling the slots. Either alone
   was worse (LoCoMo dev 54-55%; together 63.9%).
2. Replacement. When it knows a later fact replaced an earlier one, the
   replacing message is shown even if the search missed it.
3. Notes. Only where a reader should know something: (no longer true: ...),
   (said in passing: ...), (may have changed since: ...), and names the user
   gave a phrase ("home country: Sweden").
4. Housekeeping: forgetting removes the words everywhere, secrets are
   removed before storage, project memory stays in its project, and the
   memory can be read and edited as a file.

## Results

LoCoMo, conversations 2-9, 1,307 questions:

| | sourcedrecall 0.5 | Mem0 2.2.1 | plain retrieval |
|---|---|---|---|
| overall | 64.7% | 64.6% | 56.6% |
| single-hop | 74.8% | 77.9% | 66.9% |
| temporal | 55.8% | 37.2% | 49.6% |
| multi-hop | 53.6% | 61.9% | 39.3% |
| open-domain | 34.9% | 41.0% | 38.6% |
| model calls to store | 0 | 941 | 0 |
| context tokens per question | 845 | 722 | 356 |

Blind change-of-state set v4 (44 changes, 16 unchanged), reader's answers,
every flagged answer checked by hand (one judge error removed, ours, 4B):

| | sourcedrecall 0.5 | sourcedrecall 0.4.6 | plain retrieval |
|---|---|---|---|
| old state given as current, 14B reader | 2/44 | 10/44 | 7/44 |
| new state given, 14B reader | 42/44 | 34/44 | 36/44 |
| old state given as current, 4B reader | 2/44 | 11/44 | 5/44 |
| new state given, 4B reader | 35/44 | 32/44 | 28/44 |
| unchanged, answered | 16/16 | 16/16 | 16/16 |

Blind set v3 (negations, things never said, attributes never given, claims
the assistant made about the user, stale facts, paraphrased questions), 14B
reader: sourcedrecall 0/30 false memories and 23/23 paraphrased
questions answered; plain retrieval 0/30 and 23/23; Mem0 2/30 and 23/23.

## What did not work

- Tuning on a development set and expecting it to transfer. Our first
  change-of-state set moved from 33 to 40 of 50 new states found; the blind
  set moved from 28 to 30 of 44. A second, freshly written development set,
  measured once before reading it, agreed with the blind set. We now measure
  every change on a set nobody has tuned on before believing it.
- Requiring evidence that a later statement is about the same thing before
  marking an earlier one as changed. It cut wrongly marked controls by one
  and missed nine more real changes.
- Gating messages on the parser's confidence. It refused paraphrased
  questions whose answer was in the messages (42/64 against 61/64 without
  the gate); the reader declined never-mentioned questions correctly
  without it (20/20 with both readers).
- Shortening lines to save tokens. Cutting the context from 775 to 576
  tokens cost about 4 points on LoCoMo dev.

## Limitations

- Multi-hop questions (several facts from different conversations) are
  where Mem0's model calls pay off: 61.9% against our 53.6%.
- English only. The parser's rules are English.
- The install is about 1.6 GB, mostly PyTorch for the parser.
- We did not run GPT-4-class readers or judges (no paid API was used).
  With a stronger reader every system would likely score higher; we expect
  the order to hold, since our misses were mostly the reader stopping at
  the first item of a list, but that is untested. Anyone with an API key
  can rerun it from bench/REPRODUCE.md.
- All judging is by a local 14B model. Its agreement with hand labels is
  29/30 on our items, but LoCoMo scores from other papers used other
  judges and readers and are not comparable to these.
- The false-memory sets are synthetic and small (44-72 scenarios).

## Reproducing

<!-- TODO: one-command bench script, hardware, time. -->
Everything is in `bench/locomo` and `bench/false_memory`: the harness, each
system's retrieved context, the reader's answers, the judge's verdicts, and
the audit overrides.
