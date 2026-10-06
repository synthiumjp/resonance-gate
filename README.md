# sourcedrecall

Memory for AI agents that never calls a language model to store anything.

It keeps what you tell your agent, word for word and dated, and gives the
agent the right few messages when they matter. When something you said
earlier stops being true ("I moved to Brunswick"), the old line is marked
as no longer true. When you ask about something you never mentioned, the
agent is told it doesn't know. Everything runs on your machine, and you can
read, search and edit the memory yourself.

```
$ sourcedrecall-memory context "Where do I live?"
[MEMORY: what the user has told you about this] Dana Cole is the user you are talking to.
- [2026-09-25] "I work as a nurse at St Vincent's and I live in Fitzroy."  (no longer true: Dana Cole lives in Fitzroy)
- [2026-10-02] (in reply to "How was the weekend?") "Big news, I moved to Brunswick last weekend."
```

## How it compares

LongMemEval-S, 500 questions, each with about 50 past chat sessions: is a
session that holds the answer among the five the memory returns? No
language model is involved, so this is the number other memory tools
publish:

| | found in the top 5 |
|---|---|
| sourcedrecall | 98.4% |
| MemPalace (as published) | 96.6% |
| agentmemory (as published) | 95.2% |
| plain embeddings (bge-small), same messages | 96.8% |
| plain keyword search (BM25), same messages | 93.4% |

Changes of state and false memories, on held-out sets written before any
system was run, against two other memory tools that store without a
language model. Each system's memory went to the same local reader, and the
same local judge decided whether the answer states something out of date or
never said as true. Audited, one rule for every system:

| | sourcedrecall | agentmemory 0.9 | ai-memory 2.5 | plain retrieval |
|---|---|---|---|---|
| old state given as current, of 44 changes | 2 | 5 | 7 | 7 |
| new state given, of 44 | 42 | 38 | 33 | 36 |
| the same with a small (4B) reader: old state as current | 2 | 6 | 11 | |
| coding sessions behind 120 others: false memories, of 51 | 0 | 2 | 6 | 3 |
| several projects: false memories, of 32 | 0 | 9 | 4 | 3 |
| several projects: unchanged facts answered, of 13 | 8 | 12 | 5 | 7 |

The last two rows are a trade-off: sourcedrecall keeps a project's facts in
that project, so it never offers another project's fact as true here, and
it also answered "I don't know" to 5 real facts that agentmemory, which
searches every project at once, found (it also offered 9 false ones).

LoCoMo (conversations 2-9, 1,307 questions), against Mem0, with the same
local reader and judge (Qwen3-14B):

| | sourcedrecall | sourcedrecall, notes mode | Mem0 2.2.1 | plain retrieval |
|---|---|---|---|---|
| answered correctly | 64.7% | 73.1% | 64.6% | 56.6% |
| temporal questions | 56.2% | 57.4% | 37.2% | 49.6% |
| single-hop | 74.8% | 85.4% | 77.9% | 66.9% |
| multi-hop | 53.6% | 62.3% | 61.9% | 39.3% |
| model calls to store the conversations | 0 | 468 | 941 | 0 (one embedding per message) |
| context per question (tokens) | 845 | 1,230 | 722 | 356 |

Notes mode is optional: your own local model (here the same Qwen3-14B)
writes short notes once per stored conversation, labelled as its notes and
kept only where they are grounded in your own words. With the context cut
to 994 tokens it scores 71.1% (multi-hop 61.5%).

About these numbers: the answers were read and judged by local models, the
same for every system, so the comparison inside each table is fair, but the
answer scores are not comparable with published LoCoMo results, which use
GPT-4-class models and other protocols. The judge agreed with hand labels on
29 of 30 checks; the audits of its verdicts were done by an AI agent with
one rule for every system. The false-memory sets are synthetic and small
(44-100 scenarios each).

The systems hand the reader different amounts: sourcedrecall its memory
block (845 tokens a question on LoCoMo, 1,230 in notes mode), Mem0 its top
5 memories (722), agentmemory and ai-memory their top 5 results, plain
retrieval its top 3 messages (356). Mem0 2.2.1 used the same local Qwen3-14B
for its own calls, with thinking turned off and its JSON response format
removed (the local server does not support it), and dates written into the
messages because it does not accept a timestamp; this may cost it on time
questions. The other tools ran in the configuration they document for local
use without a language model; with one, they offer more than was measured
here.

LoCoMo conversations 2-9 were run for each version reported, so they are
not untouched: notes mode was changed after its first run there (72.1%)
and scored 73.1% after. Measured at: LoCoMo default f078bf4, notes mode
49561c4, LongMemEval e8b8c0f, false-memory head-to-head on the published
runs listed in `bench/false_memory/HEAD_TO_HEAD.md`. The release will be
measured again in one run.

Where it is weaker: without a model, questions that need several facts
from different conversations put together (LoCoMo multi-hop, 53.6% against
Mem0's 61.9%); notes mode closes that gap. Better retrieval alone did not:
three rankers that found more of the right messages answered no better. Only your own messages are searched, so something
only the assistant said is not found by itself.

The benchmark code, every system's retrieved context, the reader's answers
and the judge's verdicts are in `bench/` (the comparison with the other
tools: `bench/false_memory/HEAD_TO_HEAD.md`; LongMemEval:
`bench/longmemeval/`). See [the write-up](docs/launch/WRITEUP_DRAFT.md) for
the method and how to rerun it.

## What it does

- Stores your messages as you wrote them, with the date and the question
  you were answering. Nothing is summarised or rewritten by a model.
- A grammar parser (Stanza plus rules, no language model) reads each message
  for the things a reader should know: a fact that a later message replaced,
  a remark tied to its moment ("I'm in Sydney this week"), a name you gave
  something ("my home country, Sweden").
- For a question, it finds your messages two ways, through the parser's
  facts and through a search over the messages themselves, and shows them
  oldest first with those notes.
- `MEMORY.md` and a local web page show everything stored. Forget anything
  by its id and the words are removed everywhere, including from quotes.
- API keys, passwords and card numbers are removed before anything is
  stored.
- Memory about a project stays with that project. Standing instructions
  ("never add comments to my code") lead every session.
- Text you paste in for the assistant (an email, a README) is kept but not
  read as your own words, so it cannot plant an instruction.
- Sessions are stored automatically in Claude Code, Codex CLI, Gemini CLI
  and Cursor; a ChatGPT or Claude.ai data export can be imported.

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

## Privacy

Nothing leaves your machine. The memory is a folder of plain files
(`~/.sourcedrecall`). Delete the folder and it is gone.

## Licence

Apache 2.0 (see `LICENSE`).

## More

- Full documentation: [`server/README.md`](server/README.md)
- What changed in each version: [`docs/CHANGELOG.md`](docs/CHANGELOG.md)
- Rerunning the benchmarks: [`bench/REPRODUCE.md`](bench/REPRODUCE.md)
- This repository also holds the research the product came from (`experiments/`, `notebook.md`).
