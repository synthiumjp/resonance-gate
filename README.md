# sourcedrecall

Local memory for AI agents that keeps your own words. A grammar parser
decides what is stored and what has gone out of date, and its rules with a
small classifier decide whose words they are. No language model writes or
reads the memory: the small models it uses (the parser's, a search embedder
and re-ranker, a contradiction check and the pasted-text classifier) run on
your CPU. It works with any model your agent uses and needs no API key.

When you tell your agent something, sourcedrecall keeps the message as you
wrote it, with its date. When a question comes up, it hands the agent the
few messages that matter, oldest first, and marks what changed:

```
$ sourcedrecall-memory context "Where do I live?"
[MEMORY: what the user has told you about this] Dana Cole is the user you are talking to.
- [2026-09-25] "I work as a nurse at St Vincent's and I live in Fitzroy."  (no longer true: Dana Cole lives in Fitzroy)
- [2026-10-02] (in reply to "How was the weekend?") "Big news, I moved to Brunswick last weekend."
```

Text you paste in from someone else, such as an email, a review or a chat,
is shown as theirs. Memory tools that store whatever was said take a
friend's "I'm allergic to nuts" for yours. On the two newest
pre-registered held-out sets of 40 pasted claims, read by two different
local models, plain retrieval gave 23 and 28 of them back as the user's
own, agentmemory 24 and 35, and sourcedrecall 5 and 12; on 20 real pasted
emails, 14 against 7 (p=0.06). Part of the difference is that
sourcedrecall's reader more often says it does not know (on v11, 31 of the
40 pasted claims against 16 with plain retrieval). Rules added since, from the kinds of text v12
missed, bring sourcedrecall's counts to 3, 8 and 1 on the release commit,
but those sets are no longer unseen. It is far from perfect: text whose
source is named in words or places its rules do not read still passes as
yours. The cost: on the user's own writing pasted in the same way it
answered 25 of 30 where plain retrieval answered 29. This matters most
with smaller local models: with Claude Sonnet 5.5 as the reader, every
system gave back 4 or fewer of the 40 (sourcedrecall none), and on the
real emails plain retrieval 5 of 20 and sourcedrecall none.

On LoCoMo, with the same local reader and judge for every system, it
answers about as many questions as Mem0 (65.4% against 64.6%, p=0.61; with
a strict judge 50.9% against 48.5%, p=0.13) while making no model call to
store anything. With Claude Sonnet 5.5 reading and judging the same
retrieved context, 77.0% against 72.1% (p<0.001). Both leads come from
questions about dates and time, where Mem0 was at a disadvantage: it takes
no timestamp, so the dates were written into the messages, and it answers
fewer of them than plain retrieval does. On the other questions Mem0 is
ahead: 71.3% against 67.5% with the local reader (p=0.02), 81.5% against
77.6% with Claude (p=0.006). With its optional notes model sourcedrecall is
level with Mem0 there too (73.3%, p=0.23). On LongMemEval the session that
holds the answer is among the five it returns for 98.8% of 500 questions;
its answers to questions about changed facts and about time are not
clearly better than plain retrieval's.

It installs as a Claude Code plugin in a few minutes (about 1.3 GB of disk,
no PyTorch, no API key). Sessions are stored automatically in Claude Code;
its memory tools work in any MCP client, and hooks for Codex CLI, Gemini
CLI and Cursor are included but not yet tested in those apps. Your memory
is a folder of plain files on your machine.

Everything is in `bench/`, with the commands to rerun it. English only.

## How it compares

The numbers below were read and judged by local models (Qwen3-14B, and
Phi-4 as a second reader), so they are not comparable with results
published with GPT-4-class models, except where Claude Sonnet 5.5 is named
as the reader: those runs give the same retrieved context to a hosted model
(through Anthropic's Batch API; `bench/claude_runs.sh`). LongMemEval,
LoCoMo, HaluMem and the first false-memory table were measured on commit
53e0d9c (2026-10-16/17, `bench/RELEASE_53e0d9c.log`); for LoCoMo only
sourcedrecall was rerun there, and Mem0's and plain retrieval's answers are
from the 2026-10-03 run with the same questions, reader and judge. Each
held-out set's paragraph reports its run when the set was new. An
adversarial review on 2026-10-09 (`docs/REVIEW_2026-10-09.md`) found
problems with the comparisons; the tables below were rerun with its fixes
(`bench/false_memory/FAIR_RERUN.md`).

LongMemEval-S, 500 questions, each with about 50 past chat sessions: is a
session that holds the answer among the five the memory returns?

| | found in the top 5 |
|---|---|
| sourcedrecall | 98.8% |
| plain embeddings (bge-small), same messages | 96.8% |
| plain keyword search (BM25), same messages | 93.6% |
| MemPalace (as published) | 96.6% |
| agentmemory (as published) | 95.2% |

Our own plain-embeddings baseline already beats both published numbers, so
most of that gap is our harness (user messages only, sessions ranked from
messages), not the systems. The routing for advice questions was chosen on
LongMemEval's 30 preference questions, and the parser was not used here.

Changes of state and false memories, on sets written for this project
(synthetic, 32-60 scenarios each), against two other memory tools that store
without a language model and plain retrieval. Every system's memory went to
the same local reader with the same instruction, the judge saw the question
with each answer, and the answers were audited blind (the auditor saw no
system names; `bench/false_memory/FAIR_RERUN.md`). Measured on commit
53e0d9c, where every system's saved memories were read again; an answer the
2026-10-09 audit saw keeps its audited verdict, a new one the judge's:

| | sourcedrecall | agentmemory 0.9 | ai-memory 2.5 | plain retrieval |
|---|---|---|---|---|
| old state given as current, of 44 changes | 3 | 4 | 7 | 7 |
| new state given, of 44 | 42 | 37 | 33 | 36 |
| coding sessions behind 120 others: false memories, of 51 | 0 | 2 | 5 | 3 |
| several projects: false memories, of 32 | 0 | 9 | 4 | 3 |
| several projects: unchanged facts answered, of 13 | 11 | 11 | 6 | 6 |
| the three sets together: false memories, of 127 | 3 | 15 (p=0.006) | 16 (p=0.003) | 13 (p=0.02) |

p is a two-sided Fisher exact test against sourcedrecall. Set by set, only
the projects false memories against agentmemory (p=0.002) and the new state
against ai-memory (p=0.01) are clear differences; together, all are. At
commit 372c05a (2026-10-09) the counts were the same with and without
sourcedrecall's own instructions to the reader, so the difference is in
what the memories returned. These sets
have been run many times during development and some rules were written
from their errors, so they are not held out (that is v5, below). The
projects rows are a trade-off: sourcedrecall keeps a project's facts in that
project, so it never offers another project's fact as true there; most of
agentmemory's project false memories are another project's fact. These sets
hold no pasted text; on the held-out sets with pasted text, v6 and v7, see
below.

A pre-registered held-out set (v5: 120 scenarios nobody working on the
system had read, hypotheses fixed beforehand, run once): old state given as
current in 0 of 25 stated changes and 3 of 25 implied ones (plain retrieval
4 and 7; neither difference is significant), decisions recalled 10 of 10, no
declined proposal given as decided. Two hypotheses missed (the labels on
implied changes, and "no longer true" against its base rate). The one clear
difference went against sourcedrecall: asked for advice, its reader used
what the user had mentioned in 2 of 10 answers, plain retrieval's in 8 of 10
(p=0.02). Everything is in `bench/false_memory/results_v5/SUMMARY.md`.

A second pre-registered held-out set (v6: 140 scenarios, run once on
2026-10-09 under the protocol above, against all four systems) tested the
fixes made after an adversarial review. Four of eight hypotheses met: a
change that happened, old state given as current 0 of 20; hedged or
reported claims given as fact 1 of 14; in long coding sessions the
instruction or decision in force recalled 23 of 25 and a reversed one given
as current 0 of 8; standing instructions shown at the start of a session
for 11 of 12, and none of 3 idioms. Four missed. Pasted text: a claim or
instruction inside pasted material was given as the user's own in 14 of 17
(plain retrieval and agentmemory 15, ai-memory 3, which keeps only the
first line of a message); the "pasted in" marker fired on 3 of the 14, and
the reader ignored it on those too. Because of this, sourcedrecall had no
fewer false memories than the other systems on v6 (15 of 59, against 17,
17 and 10; 14 of its 15 are pasted text). Advice: the earlier mention was
used in 3 of 15 answers (plain retrieval 2); in every miss the reader said
it did not know, following the shared instruction to do so. A plan
mentioned later was taken to mean the earlier state had ended in 4 of 20
(others 4 to 6). Everything is in `bench/false_memory/results_v6/SUMMARY.md`.

Pasted text was then changed (whose text it is read from the introduction,
the writer named in the block, the rules no longer calling quoted text the
user's) and tested on a third pre-registered held-out set (v7: 140
scenarios, run once on 2026-10-10, all four systems). A claim or instruction
inside pasted material was given as the user's in 11 of 34 (32%, from 82%
on v6), against plain retrieval's 24 and agentmemory's 26 (both p<0.01);
ai-memory 2, again by keeping only first lines (it answered 4 of 16 of the
user's own pasted material). Where the "pasted in" marker fired the reader
almost never took the text for the user's; the 10 it missed had
introductions worded in ways the rules do not cover. Old state given as
current 0 of 20. Advice: the earlier mention used in 11 of 20 (plain
retrieval 7), none of 10 irrelevant mentions applied. Five of seven
hypotheses missed, including the 4-of-34 target for pasted text; in the
advice, plan and everyday parts most misses were the reader saying it did
not know with the answer in front of it. Everything is in
`bench/false_memory/results_v7/SUMMARY.md`.

Detection was then changed to read a message's shape (a short line of the
user's and a block in another voice, the introduction before or after it)
and tested on a fourth held-out set (v8: 100 scenarios, 2026-10-10). Pasted
claims or instructions given as the user's: 9 of 40 (22%; plain retrieval
16, agentmemory 20, ai-memory 2), so across v6, v7 and v8: 82%, 32%, 22%.
The pre-registered target of at most 6 of 40 was missed, and the difference from plain
retrieval was not significant (p=0.15) on this set, where pasted text misled
every system less. The marker fired on 24 of the 40; 4 marked items were
still given as the user's, 3 of them pasted instructions the reader
followed. Changes and everyday facts held (old state given as current 2 of
20, facts answered 18 of 20). Everything is in
`bench/false_memory/results_v8/SUMMARY.md`.

After v8, the writer's sentences about themselves and their general rules
were left out of pasted text unless the question names where it came from,
and long messages were cut around the question. A fifth held-out set (v9:
120 scenarios, 2026-10-11) met four of six hypotheses. Pasted claims or
instructions given as the user's: 4 of 40 (10%; plain retrieval 22,
agentmemory 27, ai-memory 3; p<0.001 against the first two), so across v6
to v9: 82%, 32%, 22%, 10%. Pooled false memories 6 of 60 (plain retrieval
24, agentmemory 29, ai-memory 6). Changes and everyday facts held (2 of 20, 16 of 20).
Two targets were missed, both costs of these changes. The user's own
material was answered in 12 of 20 (target 15; plain retrieval 17): in 4,
own text was taken for pasted and the fact was left out. Facts asked about
inside pasted text were answered in 13 of 20 (target 16; plain retrieval
20): in all 7 misses the paste was over 800 characters and the part shown
did not hold the fact. Everything is in
`bench/false_memory/results_v9/SUMMARY.md`.

After v9, pasted text and long messages were shown in longer windows cut
around the question, the writer's details were left out only for questions
about you, and your own text was recognised by how you introduce or sign
it. A sixth held-out set (v10: 120 scenarios, 2026-10-11) met five of six
hypotheses. Pasted claims or instructions given as the user's: 3 of 40 (8%;
plain retrieval 23, agentmemory 20, ai-memory 0; p<0.001 against the first
two). Facts inside pasted text were answered in 17 of 20 (plain retrieval
20, agentmemory 8), 11 of the 12 long pastes among them. Pooled false
memories 4 of 60 (plain retrieval 26, agentmemory 20, ai-memory 7); changes 1 of 20,
everyday facts 18 of 20. The miss: the user's own material was answered in
13 of 20 (target 15; plain retrieval 19). In 6 of the 7 misses the fact was
in what the reader was given and it said it did not know. A refusal is
never counted as a false memory, so read the false-memory counts with how
often each reader said it did not know: on the 40 pasted claims (where that
is the right answer) sourcedrecall 35, plain retrieval 15, agentmemory 17,
ai-memory 40; on the 20 own items (where it is wrong) 7, 1, 3 and 17.
Everything is in `bench/false_memory/results_v10/SUMMARY.md`.

After v10, other messages were shown beside the one a question is about
only when they are close to the question, and more introductions were read
("sent me", "written by", "from my boss"). A seventh held-out set (v11: 130
scenarios, 2026-10-13) was read by two readers of different model families,
Qwen3-14B and Phi-4, and met seven of eight hypotheses with the first.
Pasted claims or instructions given as the user's: 5 of 40 (plain retrieval
23, agentmemory 24, ai-memory 2; Holm-adjusted p<0.001 against the first
two); with Phi-4 5 of 40 (22, 22, 3). Facts inside pasted text 20 of 20,
changes 0 of 20, everyday facts 17 of 20. The user's own material was
answered in 24 of 30 with both readers (target 23), but 6 behind plain
retrieval (target: at most 3 behind): in all 6 the user's own writing
(a diary entry, a speech, a blog draft, two statements and a sale ad) was
taken for someone else's and its facts left out, in 5 of them although the
user had called it theirs. Without the rules paragraph the counts were the
same, so they come from what the memory returns, not from the instruction.
Said it did not know: on the 40 pasted claims sourcedrecall 31, plain
retrieval 16, agentmemory 14, ai-memory 38; on the 30 own items 6, 0, 0
and 25. Everything is in `bench/false_memory/results_v11/SUMMARY.md`.

After v11, the user's own writing brought to be read over ("my blog post",
"I write it every month") was kept as theirs, letter-shaped text was read
as someone else's, and an email pasted on its own was read with the
user's next message ("it's from a client"). An eighth held-out set (v12:
160 scenarios, 2026-10-13), with a new part of 30 real emails from the
public Enron corpus, met seven of eleven hypotheses with Qwen3-14B.
Pasted claims or instructions given as the user's: 12 of 40 (target 6;
plain retrieval 28, agentmemory 35, ai-memory 8; Holm-adjusted p 0.002 and
below 0.001 against the first two); with Phi-4 13 of 40 (32, 35, 9). Real
emails: 7 of 20 (target 6; plain retrieval 14, p=0.06); the user's own
real emails answered 10 of 10. Own material 25 of 30 (target met; 4 behind
plain retrieval, target at most 3). Facts in pasted text 19 of 20, changes
1 of 20, everyday 19 of 20. The detection itself did no worse than v11's
code on this set; a third of the pasted texts came in shapes its rules do
not read (the source named in other words, after the text, or only in a
later message), and were taken for the user's. Everything is in
`bench/false_memory/results_v12/SUMMARY.md`.

After v12, a third person named around a first-person block ("my brother,
last night:") marks it as theirs, and a small learned model judges what the
rules leave unmarked. Both were developed on a new set written from the
kinds of text v12 missed (categories only, not its items), so v11, v12 and
the real emails are no longer unseen for this code. Run again on the
release commit (53e0d9c), counts only: pasted claims or instructions given
as the user's 3 of 40 on v11 and 8 of 40 on v12 with Qwen3-14B (plain
retrieval 23 and 28, agentmemory 24 and 35, ai-memory 2 and 8), 3 and 10
with Phi-4; real emails 1 of 20 with both readers (plain retrieval 16 and
17). Own material 25 of 30 on both sets with Qwen3-14B (plain retrieval 30
and 29). With Claude Sonnet 5.5 reading the same returns (judged by
Qwen3-14B, no audit): pasted claims given as the user's 0 of 40 on both
sets (plain retrieval 0 and 2, agentmemory 1 and 3, ai-memory 1 and 4), real
emails 0 of 20 (plain retrieval 5), own material 25 and 26 of 30 (plain
retrieval 30 and 30). A strong reader mostly tells pasted text from the
user's own on its own; what sourcedrecall marks matters most with smaller
models. A new held-out set is the next test (`bench/false_memory/results_release2_*`,
`results_claude_*`).

LoCoMo (conversations 2-9, 1,307 questions), against Mem0, with the same
local reader and judge:

| | sourcedrecall | with the built-in notes model | Mem0 2.2.1 | plain retrieval |
|---|---|---|---|---|
| answered correctly | 65.4% | 67.8% (small) / 70.6% (standard) | 64.6% | 56.6% |
| temporal questions | 57.0% | 55.0% / 59.7% | 37.2% | 49.6% |
| single-hop | 75.5% | 79.4% / 81.0% | 77.9% | 66.9% |
| multi-hop | 54.0% | 55.6% / 58.6% | 61.9% | 39.3% |
| open-domain | 36.1% | 41.0% / 48.2% | 41.0% | 38.6% |
| without temporal questions | 67.5% | 70.9% / 73.3% | 71.3% | 58.3% |
| model calls to store the conversations | 0 | 468, in-process | 941 (generation and embedding) | 0 (one embedding per message) |
| what the reader is given | about 13 messages (4 to 34) | the same, and notes | 20 memories (10 per speaker) | 10 messages |
| context per question (tokens) | 682 | 1,032 / 1,025 | 722 | 356 |

Paired tests (McNemar) against Mem0: overall p=0.61; without temporal
questions p=0.02, Mem0 ahead; with the standard notes model p<0.001 and,
without temporal questions, p=0.23. Plain retrieval gets half the context
of the others, so part of its gap is budget. Notes written by Qwen3-14B
running as a local server (a model call per message, commit 49561c4) gave
73.1%.

With Claude Sonnet 5.5 as reader and judge (the same retrieved context and
prompts, Anthropic's Batch API, `bench/locomo/answer_claude.py`), closer to
how published results are measured:

| | sourcedrecall | Mem0 2.2.1 | plain retrieval |
|---|---|---|---|
| answered correctly | 77.0% | 72.1% | 69.2% |
| temporal questions | 74.8% | 33.7% | 66.3% |
| single-hop | 82.5% | 86.8% | 76.5% |
| multi-hop | 68.2% | 71.1% | 53.6% |
| open-domain | 61.4% | 65.1% | 59.0% |
| without temporal questions | 77.6% | 81.5% | 69.9% |

Without the audit's 80 wrong gold answers (below): 79.1%, 74.5%, 71.5%. On
multi-hop questions the two split 23 to 30, not a clear difference
(McNemar p=0.41); with the local reader they split 31 to 50 (p=0.045).

The lead over Mem0 with both readers comes from temporal questions, where
Mem0 was at a disadvantage: it accepts no timestamp, so dates were written
into the messages, and it answers fewer temporal questions than plain
retrieval. Without them Mem0 is ahead with both readers (p=0.02 with the
local reader, p=0.006 with Claude), on single-hop, multi-hop and
open-domain questions. Giving Mem0 the dates another way (its metadata
field) has not been tried. An audit of LoCoMo
(Penfield Labs, April 2026, github.com/dial481/locomo-audit) found 99 of its
1,540 gold answers wrong, 80 of them in these conversations. Without those
80: sourcedrecall 66.9%, with notes 69.8% (small) / 72.6% (standard) / 74.5%
(Qwen3-14B), Mem0 66.8%, plain retrieval 58.2% (`LOCOMO_AUDIT` in
`bench/locomo/score.py`). The judge prompt used here and in Mem0's
published evaluation ("be generous ... as long as it touches on the same
topic") accepted 68.5% of the audit's deliberately vague wrong answers with
our judge (`bench/locomo/judge_stress.py`). With a strict prompt (3% and 20%
of the audit's specific and vague wrong answers accepted, every gold answer
in a sample of 120 accepted; `LOCOMO_JUDGE=strict`), the same answers score:
sourcedrecall 50.9%, Mem0 48.5%, plain retrieval 42.5%; with notes 50.9% /
54.2% / 55.1%. Without the audit's 80 wrong gold answers: 52.6%, 50.4%,
43.9%; 52.6% / 56.2% / 57.0%. The order is the same under both judges;
temporal questions favour sourcedrecall (38.9% against Mem0's 23.5%, strict,
errors removed) and multi-hop questions Mem0 (37.8% against 30.0%). Mem0
was given its top 10 memories for each speaker and plain retrieval its top
10 messages; Mem0
used the same local Qwen3-14B for its own calls, with thinking off and its
JSON response format removed (the local server does not support it). The
benchmark runs sourcedrecall without its conflict model (RG_NLI=0), which
the server loads by default. These conversations were run for every version
reported here, and chose the design (messages first) and the notes models,
so they are not held out. Measured in one run on commit 53e0d9c
(`bench/RELEASE_53e0d9c.log`; 1,424 tests passed, and one parser test
failed only because the run compared against the wrong reference parser:
with the right one it passes; the strict judge in a second pass); the
Qwen3-14B notes column is from commit 49561c4. Between runs the notes change
with the text they are written from: the small model scored 68.2% on
1754180, 67.7% on 181aff3, 67.0% on 8473783 and d89d830, and 67.8% here.

HaluMem (HaluMem-Medium, its first two users), scored with the benchmark's
own code for memory updates and questions and the same local judge for both
systems: after a fact changed, the new value was given in 154 of 304 updates
(plain retrieval 96), and 184 of 352 questions were answered correctly
(plain retrieval 162), with fewer wrong answers among those the judge could
score (21% against 27%). Plain retrieval's run is from commit d6613e0
(`bench/halumem/`).

Notes are optional. A small model writes short notes once per stored
conversation, labelled as its notes and kept only where most of their words
are in what you wrote. The built-in models run inside sourcedrecall on the
CPU, with no server: small (Qwen3-0.6B trained for this, 0.5 GB) and
standard (Qwen3-1.7B, 1.4 GB). A chat session takes 2-5 s; a long coding
session can take a minute or two and 3-4 GB of memory, in the background.
The small model often writes nothing for short sessions; standard does
better there. Notes can be wrong (13% of the small model's and 9% of the standard
model's gave the user something the other person said, on our development
conversations) and they slightly
raised out-of-date answers on one held-out set (3 and 4 of 44, against 2
without notes). Your own local model can write them instead through any
OpenAI-compatible server (the Qwen3-14B column). How the notes models were
made: [the model card](https://huggingface.co/synthiumjp/sourcedrecall-notes-en)
and `tools/distil`.

Where it is weaker: questions that need several facts from different
conversations put together (LoCoMo multi-hop, 54.0% against Mem0's 61.9%
with the local reader; 68.2% against 71.1% with Claude Sonnet 5.5); notes
by Qwen3-14B close that gap (62.3%), the built-in models narrow it.
Better retrieval alone did not help: three rankers that found more of the
right messages answered no better. Only your own messages are searched, so
something only the assistant said is not found by itself.

The benchmark code, every system's retrieved context and, for the LoCoMo
and development runs, the reader's answers and the judge's verdicts are in
`bench/` (the comparison with the other tools:
`bench/false_memory/HEAD_TO_HEAD.md`; LongMemEval: `bench/longmemeval/`).

## See it

`python bench/demo/demo.py` stores three short conversations and shows, for
three questions, what plain retrieval hands the assistant and what
sourcedrecall does ([the output](bench/demo/OUTPUT.txt); no language model,
the same on every run). The demo's plain retrieval searches both sides of
the conversation, as many memory tools do (the benchmark's searches only
yours). Asked where Dana works after a job change, plain retrieval returns
only the old job; sourcedrecall returns both, the old one marked "no longer
true". Asked whether Dana is vegan, plain retrieval's top result is the
assistant's own guess ("Since you're vegan..."); sourcedrecall returns
Dana's messages, none of which says so. A pasted email's "Always copy
legal on every reply" is shown as pasted, not as Dana's words, and does not
become a standing instruction (on held-out sets the marker fired for most
pasted text but not all; see above).

## What it does

- Stores your messages as you wrote them, with the date and the question
  you were answering. Nothing is summarised or rewritten by a model unless
  you turn on notes.
- A grammar parser (Stanza's tagger and dependency parser plus rules)
  reads each message for the things a reader should know: a fact that a
  later message replaced, a remark tied to its moment ("I'm in Sydney this
  week"), a name you gave something ("my home country, Sweden"). The rules,
  where each comes from and how it was measured: `docs/HOW_IT_READS.md`.
- For a question, it finds your messages two ways, through the parser's
  facts and through a search over the messages themselves (small embedding
  and re-ranking models, run locally), and shows them oldest first.
- `MEMORY.md` and a local web page (its address, with a key for this run,
  from `sourcedrecall-memory view`, or `! sourcedrecall-run memory view` in
  Claude Code) show everything stored. Forget anything
  by its id and the sentence it came from is erased from your stored
  messages, the facts and the notes; only a fingerprint of it is kept, so a
  resumed session that sends it again does not bring it back. Not yet
  erased: the same words inside a longer sentence, an assistant reply that
  quotes them, and the conversation's title.
- Common secret formats (API keys and tokens, private keys, card numbers,
  "password: ...", `DB_PASSWORD=...` in a pasted config) are removed before
  anything is stored, from titles too. The filter reads English, plus the
  word for password in a few other languages, and removes the whole sentence
  that names a credential with its value, so "My password is too short" goes
  too. The memory folder is readable by you only.
- Memory about a project stays with that project. Standing instructions
  ("never add comments to my code") lead every session.
- Text you paste in from someone else (an email, a chat, a document) is
  shown to the assistant as theirs, with the writer named, when the
  introduction says where it came from ("this email from my landlord", "my
  boss sent me this", "translate this") or the pasted text is shaped like
  someone else's (a letter, a chat log, a review). Unless you ask about
  that text by its source, the writer's sentences about themselves and their
  general rules are left out; dates, times and places stay. It is not
  reliable: on the last two held-out sets a pasted claim or instruction was
  taken for yours in 5 of 40 (v11) and 12 of 40 (v12), against 23 and 28
  with plain retrieval, and in 7 of 20 real emails (plain retrieval 14);
  on the release commit, after rules made from v12's misses, 3, 8 and 1.
  With a strong reader such as Claude Sonnet the other systems' counts fall
  to a few of 40 too, so this matters most with smaller local models.
  Text whose source is named in words or places the rules do not read
  passes as yours. Your own pasted-looking material (drafts, speeches,
  diary entries) is answered a little less often than with plain retrieval
  (25 of 30 against 29 on v12).
- Sessions are stored automatically in Claude Code. Hooks for Codex CLI,
  Gemini CLI and Cursor are included but have not yet been tested inside
  those apps. A ChatGPT or Claude.ai data export can be imported.

## Install

In Claude Code (version 2.1.83 or later; `claude --version`):

```
/plugin marketplace add synthiumjp/sourcedrecall
/plugin install sourcedrecall@sourcedrecall
```

It asks for your name: facts are written about that name, and your words
are told from other people's by it (change it with `/plugin configure
sourcedrecall`). The first session then sets it up in the background, a
few minutes the first time. To check that it works, start a new session
and type:

```
! sourcedrecall-run memory status
```

`sourcedrecall-run memory ...` and `sourcedrecall-run import ...` run the
`sourcedrecall-memory` and `sourcedrecall-import` commands below from the
plugin's own environment; in Claude Code, start the line with `!`.

On Windows it needs Git for Windows (which Claude Code uses anyway) and
Python 3.10 to 3.13. Sessions are stored and summarised as on other
systems, but Claude Code cannot start the plugin's memory tools by itself
there; the first session after setup shows a one-line `claude mcp add`
command that turns them on.

Any other MCP client (Claude Desktop, Cursor, Windsurf, Zed, VS Code, ...):
see [CLIENTS.md](docs/CLIENTS.md). Without MCP, the command line works with any
model:

```bash
git clone https://github.com/synthiumjp/sourcedrecall && cd sourcedrecall
pip install -e ./server && sourcedrecall-setup
sourcedrecall-memory ingest chat.jsonl
sourcedrecall-memory context "Where do I live?"
```

Needs Python 3.10 to 3.13. The install takes a few minutes and about 1.3 GB of disk (0.7 GB of it models); no PyTorch.
After setup it runs offline.

Notes, optional:

```bash
pip install -e './server[notes]'
sourcedrecall-setup --notes            # small, 0.5 GB
sourcedrecall-setup --notes standard   # 1.4 GB
```

`SOURCEDRECALL_NOTES=off` turns them off again.

## Privacy

sourcedrecall sends nothing anywhere: the models run on your machine, and
the only network use is the one-time install (the Python packages, and the
models in `sourcedrecall-setup`). What it hands your agent goes to the agent's model
like any other context. If you point notes at a server of your own
(`SOURCEDRECALL_NOTES_URL`), conversations are sent to that server. The
memory is a folder of plain files (`~/.sourcedrecall`); delete the folder
and it is gone.

## Uninstall

In Claude Code, `/plugin uninstall sourcedrecall@sourcedrecall`, or
`pip uninstall sourcedrecall` if you installed it with pip. Then remove
what setup and the memory left on disk:

```
rm -rf ~/.sourcedrecall            # your memory, the parser and notes models
rm -rf ~/.cache/sourcedrecall      # the embedder, re-ranker and conflict models
```

On Windows, in PowerShell:

```
Remove-Item -Recurse -Force ~\.sourcedrecall, ~\.cache\sourcedrecall
```

The plugin keeps its own copy and environment in Claude Code's plugin data
folder, which Claude Code removes with the plugin (or in
`~/.sourcedrecall/plugin` when that folder is not set). WordNet is in
NLTK's data folder (`~/nltk_data`), which other tools may share.

## Licence

Apache 2.0 (see `LICENSE`). The models setup downloads have their own
licences, listed in `NOTICE`. The parser's models are trained on UD
English-EWT (CC BY-SA 4.0) alone; the re-ranking model is trained on MS
MARCO, which Microsoft provides for non-commercial research.

## More

- Questions people ask (is this just RAG? what about Claude Code's memory?): [`docs/FAQ.md`](docs/FAQ.md)
- Full documentation: [`server/README.md`](server/README.md)
- What changed in each version: [`docs/CHANGELOG.md`](docs/CHANGELOG.md)
- Rerunning the benchmarks: [`bench/REPRODUCE.md`](bench/REPRODUCE.md)
- This repository also holds the research the product came from (`experiments/`, `notebook.md`).
