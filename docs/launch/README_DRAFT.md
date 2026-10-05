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

LoCoMo (conversations 2-9, 1,307 questions). Every system's retrieved memory
was given to the same local reader and the same local judge (Qwen3-14B):

| | sourcedrecall 0.5 | Mem0 2.2.1 | plain retrieval |
|---|---|---|---|
| answered correctly | 64.7% | 64.6% | 56.6% |
| temporal questions | 56.2% | 37.2% | 49.6% |
| single-hop | 74.8% | 77.9% | 66.9% |
| multi-hop | 53.6% | 61.9% | 39.3% |
| model calls to store the conversations | 0 | 941 | 0 (one embedding per message) |
| context per question (tokens) | 845 | 722 | 356 |

Changes of state, on a test set written before any system was run (44
things that changed, 16 that did not). The reader's answer is judged:

| | sourcedrecall 0.5 | plain retrieval |
|---|---|---|
| answer gives the old state as current (14B reader) | 2/44 | 7/44 |
| answer gives the new state (14B reader) | 42/44 | 36/44 |
| answer gives the old state as current (4B reader) | 2/44 | 5/44 |
| answer gives the new state (4B reader) | 35/44 | 28/44 |
| unchanged things answered | 16/16 | 16/16 |

"New state given" counts answers containing the expected words; a few
answers give it in other words (ours 3, plain retrieval 2, with the 4B
reader).

For coding assistants, each test scenario was stored after a background of
120 ordinary debugging sessions (held-out sets, audited):

| | sourcedrecall 0.5 | plain retrieval |
|---|---|---|
| answer states an out-of-date or never-confirmed setup | 0/51 | 3/51 |
| answer gives the new setup after a change ("moved CI to GitHub Actions") | 14/14 | 11/14 |
| a fact from another project offered as true of this one | 0/13 | 2/13 |
| a preference said in another project, found when asked here | 4/8 | 4/8 |

About these numbers: every answer was read and judged by a local model
(Qwen3-14B), the same for every system, so the comparison inside each table
is fair, but the scores are not comparable with published LoCoMo results,
which use GPT-4-class models and other protocols. The judge agreed with hand
labels on 29 of 30 checks. The false-memory and coding sets are synthetic and
small (44-100 scenarios each); the held-out ones were written before any
system was run. Mem0 used the same local model for its own calls. To rerun
everything with another model, see `bench/REPRODUCE.md`.

Where it is weaker: questions that need several facts from different
conversations put together (LoCoMo multi-hop, 53.6% against 61.9%). Mem0 makes a model call for
every exchange and merges facts as it goes; sourcedrecall does not.

The benchmark code, every system's retrieved context, the reader's answers
and the judge's verdicts are in `bench/`. See [the write-up](WRITEUP_DRAFT.md)
for the method and how to rerun it.

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
- Memory about a project stays with that project.

## Install

In Claude Code:

```
/plugin marketplace add synthiumjp/sourcedrecall
/plugin install sourcedrecall@sourcedrecall
```

Any other MCP client (Claude Desktop, Cursor, Windsurf, Zed, VS Code, ...):
see [CLIENTS.md](../CLIENTS.md). Without MCP, the command line works with any
model:

```bash
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

<!-- TODO: confirm -->
