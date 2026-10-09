# sourcedrecall

Memory for AI agents that keeps your own words. It uses no generative
language model to store anything (unless you turn on the optional notes).

It keeps what you tell your agent, word for word and dated, and gives the
agent the few messages that matter for a question, oldest first, so a later
message can be read as updating an earlier one. A grammar parser adds short
notes where it can tell: a fact a later message replaced ("no longer true"),
a remark tied to its moment, a standing instruction, a decision you made
with the assistant. When you ask about something you never mentioned, the
agent is told it doesn't know. Everything runs on your machine, and you can
read, search and edit the memory yourself. English only.

```
$ sourcedrecall-memory context "Where do I live?"
[MEMORY: what the user has told you about this] Dana Cole is the user you are talking to.
- [2026-09-25] "I work as a nurse at St Vincent's and I live in Fitzroy."  (no longer true: Dana Cole lives in Fitzroy)
- [2026-10-02] (in reply to "How was the weekend?") "Big news, I moved to Brunswick last weekend."
```

The labels fire when a later message states the change in a form the parser
knows (moved to, started at, a new value of the same kind). On a held-out
set they fired rarely on changes that were only implied (2 of 25), and the
right answers there came from the dated messages, not the labels.

## How it compares

All numbers below were read and judged by local models (Qwen3-14B), so they
are not comparable with results published with GPT-4-class models. An
adversarial review on 2026-10-09 (`docs/REVIEW_2026-10-09.md`) found
problems with the comparisons; they are listed with each table and are
being fixed before these numbers are used for any claim.

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
system names; `bench/false_memory/FAIR_RERUN.md`):

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
hold no pasted text; on the held-out set v6, which does, sourcedrecall had
no fewer false memories than the others (below).

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

LoCoMo (conversations 2-9, 1,307 questions), against Mem0, with the same
local reader and judge:

| | sourcedrecall | with the built-in notes model | with notes by Qwen3-14B | Mem0 2.2.1 | plain retrieval |
|---|---|---|---|---|---|
| answered correctly | 64.7% | 68.2% (small) / 70.3% (standard) | 73.1% | 64.6% | 56.6% |
| temporal questions | 53.5% | 58.9% / 57.4% | 57.4% | 37.2% | 49.6% |
| single-hop | 75.5% | 79.0% / 81.6% | 85.4% | 77.9% | 66.9% |
| multi-hop | 52.3% | 55.2% / 59.0% | 62.3% | 61.9% | 39.3% |
| model calls to store the conversations | 0 | 468, in-process | 468, to a local server | 941 (generation and embedding) | 0 (one embedding per message) |
| context per question (tokens) | 696 | 1,048 / 1,037 | 1,230 | 722 | 356 |

The tie with Mem0 comes from temporal questions, where Mem0 was handicapped:
it accepts no timestamp, so dates were written into the messages. Without
them, sourcedrecall answers 67.4% and Mem0 71.3%, and Mem0 leads on
single-hop, multi-hop and open-domain questions. An audit of LoCoMo
(Penfield Labs, April 2026, github.com/dial481/locomo-audit) found 99 of its
1,540 gold answers wrong, 80 of them in these conversations. Without those
80: sourcedrecall 66.2%, with notes 69.4% (small) / 72.3% (standard) / 74.5%
(Qwen3-14B), Mem0 66.8%, plain retrieval 58.2% (`LOCOMO_AUDIT` in
`bench/locomo/score.py`). Mem0 was given its top 10
memories for each speaker and plain retrieval its top 10 messages; Mem0
used the same local Qwen3-14B for its own calls, with thinking off and its
JSON response format removed (the local server does not support it). The
benchmark runs sourcedrecall without its conflict model (RG_NLI=0), which
the server loads by default. These conversations were run for every version
reported here, and chose the design (messages first) and the notes models,
so they are not held out. Measured in one run on commit 1754180
(`bench/RELEASE_1754180.log`; 1,176 tests passed); the Qwen3-14B notes
column is from commit 49561c4.

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
become a standing instruction (on the held-out set v6 the pasted marker
often did not fire, and the reader ignored it when it did; see above).

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
  by its id and the sentence it came from is erased from the stored
  messages, the facts and the notes; only a fingerprint of it is kept, so a
  resumed session that sends it again does not bring it back.
- Common secret formats (API keys and tokens, private keys, card numbers,
  "password: ...", `DB_PASSWORD=...` in a pasted config) are removed before
  anything is stored, from titles too. The memory folder is readable by you
  only.
- Memory about a project stays with that project. Standing instructions
  ("never add comments to my code") lead every session.
- Pasted text is open. The parser tries not to store a pasted claim or
  instruction as your fact or your standing instruction (on the held-out
  set v6, none of the 14 it got wrong had been stored that way), but the
  message is still shown to the assistant, the "pasted in" marker fired on
  only 3 of those 14, and the reader took a pasted claim or instruction
  for yours in 14 of 17.
- Sessions are stored automatically in Claude Code. Hooks for Codex CLI,
  Gemini CLI and Cursor are included but have not yet been tested inside
  those apps. A ChatGPT or Claude.ai data export can be imported.

## Install

In Claude Code:

```
/plugin marketplace add synthiumjp/sourcedrecall
/plugin install sourcedrecall@sourcedrecall
```

Any other MCP client (Claude Desktop, Cursor, Windsurf, Zed, VS Code, ...):
see [CLIENTS.md](docs/CLIENTS.md). Without MCP, the command line works with any
model:

```bash
git clone https://github.com/synthiumjp/sourcedrecall && cd sourcedrecall
pip install -e ./server && sourcedrecall-setup
sourcedrecall-memory ingest chat.jsonl
sourcedrecall-memory context "Where do I live?"
```

Needs Python 3.10+. The install is about 0.9 GB with its models and takes a minute or two; no PyTorch.
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

## Licence

Apache 2.0 (see `LICENSE`).

## More

- Full documentation: [`server/README.md`](server/README.md)
- What changed in each version: [`docs/CHANGELOG.md`](docs/CHANGELOG.md)
- Rerunning the benchmarks: [`bench/REPRODUCE.md`](bench/REPRODUCE.md)
- This repository also holds the research the product came from (`experiments/`, `notebook.md`).
