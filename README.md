# sourcedrecall

Local memory for AI agents that keeps your own words. A grammar parser, not
a language model, decides what is stored, whose words they are, and what
has gone out of date. It runs on your CPU, works with any model your agent
uses, and needs no API key.

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
emails, 14 against 7. It is far from perfect: text whose source is named
in words or places its rules do not read still passes as yours. The cost:
on the user's own writing pasted in the same way it answered 25 of 30
where plain retrieval answered 29.

On LoCoMo, with the same local reader and judge for every system, it is
level with Mem0 (50.3% against 48.5% with a strict judge; 65.3% against
64.6% with the benchmark's usual judge) while making no model call to
store anything; Mem0 is ahead on questions that combine several facts.
On LongMemEval's knowledge-update questions, where a fact changes over a
long history, it answered 64 of 78 against plain retrieval's 61 with the
same reader and judge, and 73 of 133 questions about time and order
against 64.

It installs as a Claude Code plugin in a minute or two (about 1.5 GB of
disk, no PyTorch, no API key), uses about 400 MB of memory, and answers in
about 50 ms. It also works with Codex CLI, Gemini CLI, Cursor and any MCP
client. Your memory is a folder of plain files on your machine.

Everything is in `bench/`, with the commands to rerun it. English only.

## How it compares

All numbers below were read and judged by local models (Qwen3-14B), so they
are not comparable with results published with GPT-4-class models. An
adversarial review on 2026-10-09 (`docs/REVIEW_2026-10-09.md`) found
problems with the comparisons; the tables below were rerun with its fixes
(`bench/false_memory/FAIR_RERUN.md`).

LongMemEval-S, 500 questions, each with about 50 past chat sessions: is a
session that holds the answer among the five the memory returns?

| | found in the top 5 |
|---|---|
| sourcedrecall | 98.8% |
| plain embeddings (bge-small), same messages | 96.8% |
| plain keyword search (BM25), same messages | 93.4% |
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
with each answer, and every answer was audited blind (the auditor saw no
system names; `bench/false_memory/FAIR_RERUN.md`; measured at commit
372c05a, 2026-10-09):

| | sourcedrecall | agentmemory 0.9 | ai-memory 2.5 | plain retrieval |
|---|---|---|---|---|
| old state given as current, of 44 changes | 2 | 4 | 8 | 5 |
| new state given, of 44 | 42 | 38 | 33 | 36 |
| coding sessions behind 120 others: false memories, of 51 | 0 | 2 | 5 | 3 |
| several projects: false memories, of 32 | 0 | 8 | 4 | 3 |
| several projects: unchanged facts answered, of 13 | 11 | 11 | 6 | 6 |
| the three sets together: false memories, of 127 | 2 | 14 (p=0.003) | 17 (p=0.0005) | 11 (p=0.02) |

p is a two-sided Fisher exact test against sourcedrecall. Set by set, only
the projects false memories against agentmemory (p=0.005) and the new state
against ai-memory (p=0.01) are clear differences; together, all are. The
counts were the same with and without sourcedrecall's own instructions to
the reader, so the difference is in what the memories returned. These sets
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
24, agentmemory 29). Changes and everyday facts held (2 of 20, 16 of 20).
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
memories 4 of 60 (plain retrieval 26, agentmemory 20); changes 1 of 20,
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

LoCoMo (conversations 2-9, 1,307 questions), against Mem0, with the same
local reader and judge:

| | sourcedrecall | with the built-in notes model | with notes by Qwen3-14B | Mem0 2.2.1 | plain retrieval |
|---|---|---|---|---|---|
| answered correctly | 65.3% | 67.0% (small) / 70.2% (standard) | 73.1% | 64.6% | 56.6% |
| temporal questions | 55.4% | 53.5% / 56.6% | 57.4% | 37.2% | 49.6% |
| single-hop | 76.1% | 78.8% / 80.7% | 85.4% | 77.9% | 66.9% |
| multi-hop | 52.3% | 54.4% / 60.7% | 62.3% | 61.9% | 39.3% |
| model calls to store the conversations | 0 | 468, in-process | 468, to a local server | 941 (generation and embedding) | 0 (one embedding per message) |
| context per question (tokens) | 687 | 1,036 / 1,030 | 1,230 | 722 | 356 |

The tie with Mem0 comes from temporal questions, where Mem0 was handicapped:
it accepts no timestamp, so dates were written into the messages. Without
them, sourcedrecall answers 67.4% and Mem0 71.3%, and Mem0 leads on
single-hop, multi-hop and open-domain questions. An audit of LoCoMo
(Penfield Labs, April 2026, github.com/dial481/locomo-audit) found 99 of its
1,540 gold answers wrong, 80 of them in these conversations. Without those
80: sourcedrecall 66.7%, with notes 68.5% (small) / 71.9% (standard) / 74.5%
(Qwen3-14B), Mem0 66.8%, plain retrieval 58.2% (`LOCOMO_AUDIT` in
`bench/locomo/score.py`). The judge prompt used here and in Mem0's
published evaluation ("be generous ... as long as it touches on the same
topic") accepted 68.5% of the audit's deliberately vague wrong answers with
our judge (`bench/locomo/judge_stress.py`). With a strict prompt (3% and 20%
of the audit's specific and vague wrong answers accepted, every gold answer
in a sample of 120 accepted; `LOCOMO_JUDGE=strict`), the same answers score:
sourcedrecall 50.3%, Mem0 48.5%, plain retrieval 42.5%; with notes 50.0% /
52.9% / 55.1%. Without the audit's 80 wrong gold answers: 51.7%, 50.4%,
43.9%; 51.6% / 54.8% / 57.0%. The order is the same under both judges;
temporal questions favour sourcedrecall (35.9% against Mem0's 23.5%, strict,
errors removed) and multi-hop questions Mem0 (37.8% against 27.2%). Mem0
was given its top 10 memories for each speaker and plain retrieval its top
10 messages; Mem0
used the same local Qwen3-14B for its own calls, with thinking off and its
JSON response format removed (the local server does not support it). The
benchmark runs sourcedrecall without its conflict model (RG_NLI=0), which
the server loads by default. These conversations were run for every version
reported here, and chose the design (messages first) and the notes models,
so they are not held out. Measured in one run on commit d89d830
(`bench/RELEASE_d89d830.log`; 1,331 tests passed; the strict judge in a
second pass); the Qwen3-14B notes column is from commit 49561c4. Between
runs the notes change with the text they are written from: the small model
scored 68.2% on 1754180, 67.7% on 181aff3 and 67.0% on 8473783 and here,
and each of the 16 questions it lost since 181aff3 has different notes in
its context.

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
conversations put together (LoCoMo multi-hop, 52.3% against Mem0's 61.9%);
notes by Qwen3-14B close that gap (62.3%), the built-in models narrow it.
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
  from `sourcedrecall-memory view`) show everything stored. Forget anything
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
  with plain retrieval, and in 7 of 20 real emails (plain retrieval 14).
  Text whose source is named in words or places the rules do not read
  passes as yours. Your own pasted-looking material (drafts, speeches,
  diary entries) is answered a little less often than with plain retrieval
  (25 of 30 against 29 on v12).
- Sessions are stored automatically in Claude Code. Hooks for Codex CLI,
  Gemini CLI and Cursor are included but have not yet been tested inside
  those apps. A ChatGPT or Claude.ai data export can be imported.

## Install

In Claude Code:

```
/plugin marketplace add synthiumjp/sourcedrecall
/plugin install sourcedrecall@sourcedrecall
```

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

Needs Python 3.10 to 3.13. The install takes a minute or two and about 1.5 GB of disk (0.85 GB of it models); no PyTorch. A running memory server uses about 400 MB of RAM and answers a question in about 50 ms once loaded.
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
the only network use is the one-time model download in
`sourcedrecall-setup`. What it hands your agent goes to the agent's model
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

The plugin keeps its own copy and environment in Claude Code's plugin data
folder, which Claude Code removes with the plugin (or in
`~/.sourcedrecall/plugin` when that folder is not set). WordNet is in
NLTK's data folder (`~/nltk_data`), which other tools may share.

## Licence

Apache 2.0 (see `LICENSE`). The models setup downloads have their own
licences, listed in `NOTICE`; the parser's English models are trained on
treebanks that include some non-commercial text.

## More

- Questions people ask (is this just RAG? what about Claude Code's memory?): [`docs/FAQ.md`](docs/FAQ.md)
- Full documentation: [`server/README.md`](server/README.md)
- What changed in each version: [`docs/CHANGELOG.md`](docs/CHANGELOG.md)
- Rerunning the benchmarks: [`bench/REPRODUCE.md`](bench/REPRODUCE.md)
- This repository also holds the research the product came from (`experiments/`, `notebook.md`).
