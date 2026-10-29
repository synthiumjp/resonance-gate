# sourcedrecall

Local memory for Claude Code and other agents that keeps the record: what
you said, in your own words and with dates, and what happened in your
coding sessions (the commands run, what failed, what fixed it, why
something was decided). Claude Code's own memory is notes Claude writes for
itself; sourcedrecall keeps the source those notes are written from, and
marks what has gone out of date.

No language model writes or reads the memory. A grammar parser decides what
is stored and what a later message replaced, and small models on your CPU
(the parser's, a search embedder and re-ranker, a contradiction check and a
pasted-text classifier) find the right messages. It works with any model
your agent uses and needs no API key. The memory is a folder of plain files
on your machine.

```
$ sourcedrecall-memory context "Where do I live?"
[MEMORY: what the user has told you about this] Dana Cole is the user you are talking to.
- [2026-09-25] "I work as a nurse at St Vincent's and I live in Fitzroy."  (no longer true: Dana Cole lives in Fitzroy)
- [2026-10-02] (in reply to "How was the weekend?") "Big news, I moved to Brunswick last weekend."
```

In Claude Code, `/recall how did we fix the login test` searches this
project's past sessions and answers with the date and session of each thing
it uses. The search tool's description asks Claude to use it when you say
"last time" or an error looks familiar.

It installs as a Claude Code plugin in a few minutes (about 1.3 GB of disk,
no PyTorch). English only. Every number below is in `bench/`, with the
commands to rerun it.

## Beside Claude Code's memory

sourcedrecall is meant to run with Claude Code's memory, not instead of it.
The session-start summary leaves out what the project's `MEMORY.md` already
says. We compared the two on three kinds of question, with Claude Code's
memory simulated: Claude Sonnet 5.5 kept a memory folder session by session
following Claude Code's published memory guidance (`bench/claude_memory.py`),
and the reader was given every file in the folder, which is more than
Claude Code loads. It is a simulation, not Claude Code itself
(`bench/native_memory/`).

Past coding sessions. On 10 public repositories (311 sessions from SWE-chat,
136 questions about earlier sessions such as how a failing test was fixed or
where a change was made; pre-registered, held out, questions checked before
any answer was read; Qwen3-14B reading and judging):

| | answered |
|---|---|
| Claude Code's memory (simulated) | 77 (56.6%) |
| sourcedrecall | 98 (72.1%) |
| both together | 110 (80.9%) |
| plain search over the same session passages | 101 (74.3%) |

Both together answered 40 that the memory folder alone missed and missed 7
it answered (p<0.001). The pre-registration planned a Sonnet writer through
the API; with no API credit it ran as Claude Code subagents with the same
instructions, on 10 of the 20 held-out repositories drawn at random. sourcedrecall alone is not better than a plain
search over the session passages (98 against 101): what helps is that the
sessions are kept and searched at all, which Claude Code does not do. With
Phi-4 as the reader, on the 102 questions whose context fits its window:
memory folder 51.0%, sourcedrecall 74.5%, both 66.7% (the longer combined
context costs this smaller reader more than it adds). On all 20 held-out
repositories (268 questions) with a Qwen3-14B writer, which kept a far
poorer folder and is unfair to Claude Code's memory: 23.1%, 67.9%, 70.9%,
plain search 70.9% (`docs/PREREG_CODING_V1.md`).

Personal facts in long chats (LoCoMo, 1,307 questions). Here Claude Code's
memory is better: 76.6% against sourcedrecall's 65.6% with the local reader,
86.5% against 77.2% with Claude Sonnet 5.5 reading (both judged by
Qwen3-14B), on every kind of question. It gave the reader about 10,800
tokens a question; sourcedrecall about 690. Both together: 81.9% (121
answered that the folder alone missed, 51 the other way, p<0.001).

Pasted text (the pre-registered sets v11 and v12, below). Claude's notes
rarely took a pasted claim for the user's: 5 and 11 of 40 with the local
reader, sourcedrecall 3 and 8, plain retrieval 23 and 28. The notes lost
more of what was inside the pasted text (facts asked about it answered in 15
and 11 of 20, sourcedrecall 20 and 19) and kept more of the user's own
pasted writing (27 and 29 of 30, sourcedrecall 25 and 25).

So the case for adding it: your coding history and your exact words are
kept and can be searched, with dates and sources, and the two together
answer more than either alone. It is not better memory of personal facts
than Claude Code's own.

## How it compares with other memory tools

The numbers below were read and judged by local models (Qwen3-14B, and
Phi-4 as a second reader), so they are not comparable with results
published with GPT-4-class models, except where Claude Sonnet 5.5 is named
as the reader. Unless a paragraph says otherwise they were measured in one
run on commit 3671a09 (2026-10-28/29, `bench/RELEASE_3671a09.log`, 1,514
tests passed). An adversarial review on 2026-10-09
(`docs/REVIEW_2026-10-09.md`) found problems with the comparisons; the
tables were rerun with its fixes (`bench/false_memory/FAIR_RERUN.md`), and
reviews on 2026-10-21 and 2026-10-28 checked the claims here against their
result files.

LoCoMo (conversations 2-9, 1,307 questions), against Mem0, with the same
local reader and judge:

| | sourcedrecall | with the built-in notes model | Mem0 2.2.1 | plain retrieval |
|---|---|---|---|---|
| answered correctly | 65.4% | 67.8% (small) / 71.0% (standard) | 64.6% | 56.6% |
| temporal questions | 55.8% | 55.0% / 60.1% | 37.2% | 49.6% |
| single-hop | 76.2% | 79.9% / 81.4% | 77.9% | 66.9% |
| multi-hop | 53.1% | 53.6% / 59.0% | 61.9% | 39.3% |
| open-domain | 36.1% | 42.2% / 48.2% | 41.0% | 38.6% |
| without temporal questions | 67.8% | 70.9% / 73.7% | 71.3% | 58.3% |
| language-model calls to store the conversations | 0 | 468, in-process | 941 (generation and embedding) | 0 (one embedding per message) |
| context per question (tokens) | 685 | 1,035 / 1,028 | 722 | 356 |

Paired tests (McNemar) against Mem0: overall p=0.61; without temporal
questions p=0.03, Mem0 ahead. With the small notes model p=0.03 overall and
level without temporal questions (p=0.85); with the standard one p<0.001
overall, p=0.15 without. The lead comes from temporal questions, where Mem0
was at a disadvantage: it takes no timestamp, so the dates were written
into the messages, and it answers fewer of them than plain retrieval does.
Giving Mem0 the dates another way (its metadata field) has not been tried.
Plain retrieval gets half the context of the others, so part of its gap is
budget. Mem0's and plain retrieval's answers are from the 2026-10-03 run
with the same questions, reader and judge; only sourcedrecall was rerun.
These conversations chose the design and the notes models, so they are not
held out.

With Claude Sonnet 5.5 reading and judging (contexts retrieved on the
earlier commit 53e0d9c, Anthropic's Batch API, `bench/locomo/answer_claude.py`;
not rerun on 3671a09 while API credit is out):

| | sourcedrecall | Mem0 2.2.1 | plain retrieval |
|---|---|---|---|
| answered correctly | 77.0% | 72.1% | 69.2% |
| temporal questions | 74.8% | 33.7% | 66.3% |
| single-hop | 82.5% | 86.8% | 76.5% |
| multi-hop | 68.2% | 71.1% | 53.6% |
| open-domain | 61.4% | 65.1% | 59.0% |
| without temporal questions | 77.6% | 81.5% | 69.9% |

Without temporal questions Mem0 is ahead here too (p=0.006). An audit of
LoCoMo (Penfield Labs, April 2026, github.com/dial481/locomo-audit) found 99
of its 1,540 gold answers wrong, 80 of them in these conversations, and the
judge prompt used here and in Mem0's published evaluation ("be generous")
accepted 68.5% of the audit's deliberately vague wrong answers
(`bench/locomo/judge_stress.py`). With a strict judge prompt
(`LOCOMO_JUDGE=strict`) the order stays the same; the strict figures for
this commit are in `bench/RELEASE_3671a09.log`.

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
messages), not the systems. Its answers to questions about changed facts
(63 of 78) and about time (72 of 133) are not clearly better than plain
retrieval's.

Changes of state and false memories, on sets written for this project
(synthetic, 32-60 scenarios each), against two other memory tools that store
without a language model and plain retrieval. Every system's memory went to
the same local reader with the same instruction, the judge saw the question
with each answer, and the answers were audited blind; an answer the
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
against ai-memory (p=0.01) are clear differences. These sets have been run
many times during development and some rules were written from their
errors, so they are not held out. sourcedrecall keeps a project's facts in
that project, so it never offers another project's fact as true there; most
of agentmemory's project false memories are another project's fact.

Pasted text. Text you paste in from someone else (an email, a review, a
chat) is shown as theirs. Memory tools that store whatever was said take a
friend's "I'm allergic to nuts" for yours. This was tested on eight
pre-registered held-out sets, v5 to v12, each run once when new
(`docs/RESULTS_HISTORY.md`). On the two newest, a pasted claim or
instruction was given back as the user's own:

| of 40 pasted claims | sourcedrecall | agentmemory | ai-memory | plain retrieval |
|---|---|---|---|---|
| v11, when new (Qwen3-14B / Phi-4) | 5 / 5 | 24 / 22 | 2 / 3 | 23 / 22 |
| v12, when new | 12 / 13 | 35 / 35 | 8 / 9 | 28 / 32 |
| v11 on 3671a09 | 3 / 3 | 24 / 22 | 2 / 3 | 23 / 22 |
| v12 on 3671a09 | 8 / 10 | 35 / 35 | 8 / 9 | 28 / 32 |

v12 also held 20 real emails from the public Enron corpus with a writer's
claim in them: given as the user's 7 of 20 when new, 5 of 20 on 3671a09
with either reader (plain retrieval 14). A separate held-out set of 20 real
pasted emails (counts only, not pre-registered or audited): 7 of 20 when
first run end to end, 1 of 20 on 3671a09 (plain retrieval 16 and 17). Rules were
added after v12 from the kinds of text it missed, so on 3671a09 these sets
are no longer unseen. ai-memory's low counts come from keeping only the
first line of a message: it answered 5 to 11 of 30 of the user's own pasted
material, sourcedrecall 25 of 30 on both sets, plain retrieval 30 and 29.
Part of sourcedrecall's lead is that its reader more often says it does not
know (on v11, 31 of the 40 pasted claims against 16 with plain retrieval).
Text whose source is named in words or places its rules do not read still
passes as yours. This matters most with smaller models: with Claude Sonnet
5.5 reading (the returns of 53e0d9c), every system gave back 4 or fewer of
the 40 (sourcedrecall none), and on the separate real-email set plain
retrieval 5 of 20 and sourcedrecall none.

Facts about other people and things that change. On MemoryAgentBench's
FactConsolidation sets (long numbered lists of facts where a later fact
replaces an earlier one; pre-registered, `docs/PREREG_FACTCONSOL_V1.md`),
sourcedrecall is below plain retrieval:

| correct of 100 (context tokens) | sourcedrecall, first run | after the fix | plain retrieval |
|---|---|---|---|
| one fact, 32k list | 49 (2,206) | 84 (884) | 89 (166) |
| one fact, 64k list | 40 (2,260) | 80 (949) | 94 (165) |
| two-step, 32k list | 2 (2,559) | 10 (1,151) | 8 (171) |
| two-step, 64k list | 7 (2,294) | 7 (1,501) | 10 (168) |

The first run showed that facts about others were hardly marked as
replaced; the fix was built on the development lists only and the held-out
lists were run once more with it. sourcedrecall is still below on three of
the four, with five to nine times the context; with Phi-4 reading it is
within 4 to 5 points on single facts and level on two-step ones.

HaluMem (HaluMem-Medium, its first two users), scored with the benchmark's
own code and the same local judge for both systems: after a fact changed,
the new value was given in 155 of 304 updates (plain retrieval 96), and 186
of 352 questions were answered correctly (plain retrieval 162). Measured on
012fcca; plain retrieval's run is from commit d6613e0 (`bench/halumem/`).

Where it is weaker: personal facts against Claude Code's own memory (above);
questions that need several facts from different conversations put together
(LoCoMo multi-hop, 53.1% against Mem0's 61.9%; the standard notes model
narrows it to 59.0%); facts about other things that change, against plain
retrieval; and your own writing pasted in, which it answers a little less
often than plain retrieval (25 of 30 against 29 or 30). Only your own
messages are searched in chat memory, so something only the assistant said
is not found by itself (coding history searches both).

## Notes, optional

A small model writes short notes once per stored conversation, labelled as
its notes and kept only where most of their words are in what you wrote.
The built-in models run inside sourcedrecall on the CPU, with no server:
small (Qwen3-0.6B trained for this, 0.5 GB) and standard (Qwen3-1.7B, 1.4
GB). A chat session takes 2-5 s; a long coding session can take a minute or
two and 3-4 GB of memory, in the background. Notes can be wrong (13% of the
small model's and 9% of the standard model's gave the user something the
other person said, on our development conversations). Your own local model
can write them instead through any OpenAI-compatible server. How the notes
models were made: [the model card](https://huggingface.co/synthiumjp/sourcedrecall-notes-en)
and `tools/distil`.

## See it

`python bench/demo/demo.py` stores three short conversations and shows, for
three questions, what plain retrieval hands the assistant and what
sourcedrecall does ([the output](bench/demo/OUTPUT.txt); no language model,
the same on every run). Asked where Dana works after a job change, plain
retrieval returns only the old job; sourcedrecall returns both, the old one
marked "no longer true". Asked whether Dana is vegan, plain retrieval's top
result is the assistant's own guess ("Since you're vegan..."); sourcedrecall
returns Dana's messages, none of which says so. A pasted email's "Always
copy legal on every reply" is shown as pasted, not as Dana's words, and does
not become a standing instruction.

## What it does

- Stores your messages as you wrote them, with the date and the question
  you were answering. Nothing is summarised or rewritten by a model unless
  you turn on notes.
- Stores what happened in each Claude Code session: the commands run and
  whether they failed (with up to three of the error lines), the files
  edited, and the reasons given, as dated passages per project.
  `history_search`, `/recall` and `sourcedrecall-memory history` search
  them. `sourcedrecall-run import claude-code` stores your past sessions
  (two months of one developer's sessions, 23 sessions and 382 MB, took
  about 4 minutes on an M3 Mac).
- A grammar parser (Stanza's tagger and dependency parser plus rules)
  reads each message for the things a reader should know: a fact that a
  later message replaced, a remark tied to its moment ("I'm in Sydney this
  week"), a name you gave something ("my home country, Sweden"). The rules,
  where each comes from and how it was measured: `docs/HOW_IT_READS.md`.
- For a question, it finds your messages two ways, through the parser's
  facts and through a search over the messages themselves, and shows them
  oldest first.
- `MEMORY.md` and a local web page (its address, with a key for this run,
  from `sourcedrecall-memory view`, or `! sourcedrecall-run memory view` in
  Claude Code) show everything stored, including the coding history. Forget
  anything by its id and the sentence it came from is erased from your
  stored messages, the facts and the notes; only a fingerprint of it is
  kept, so a resumed session that sends it again does not bring it back.
  The same words inside a longer message, or quoted in an assistant reply,
  are taken out too (for sentences of three words or more). Not erased: the
  same thing said in other words. Every forget, correction and confirmation
  is logged with its time and whether it came through the agent's tools or
  the command line, without the fact's words.
- Common secret formats (API keys and tokens, private keys, card numbers,
  "password: ...", `--password` flags, `user:password@host`,
  `DB_PASSWORD=...` in a pasted config) are removed before anything is
  stored, from titles too. The filter reads English, plus the word for
  password in a few other languages, and removes the whole sentence that
  names a credential with its value, so "My password is too short" goes
  too. The memory folder is readable by you only.
- A change said in the same session as the old fact ("I use Postgres" ...
  "we switched to SQLite") is not yet marked; across sessions it is.
- Memory about a project stays with that project. Standing instructions
  ("never add comments to my code") lead every session; a rule inside a
  long pasted document does not become one.
- Text you paste in from someone else is shown to the assistant as theirs,
  with the writer named, when the introduction says where it came from
  ("this email from my landlord", "my boss sent me this") or the text is
  shaped like someone else's (a letter, a chat log, a review). Unless you
  ask about that text by its source, the writer's sentences about
  themselves and their general rules are left out; dates, times and places
  stay. It is not reliable (above).
- Sessions are stored automatically in Claude Code. Its memory tools work in
  any MCP client. Hooks for Codex CLI, Gemini CLI and Cursor are included
  but have not yet been tested inside those apps. A ChatGPT or Claude.ai
  data export can be imported.

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

Needs Python 3.10 to 3.13. The install takes a few minutes and about 1.3 GB
of disk (0.7 GB of it models); no PyTorch. After setup it runs offline.
`server/constraints.txt` lists the versions a fresh install was tested with
(`pip install -c server/constraints.txt -e ./server`); the plugin uses them
where they install.

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
models in `sourcedrecall-setup`). What it hands your agent goes to the
agent's model like any other context. If you point notes at a server of
your own (`SOURCEDRECALL_NOTES_URL`), conversations are sent to that server.
The memory is a folder of plain files (`~/.sourcedrecall`); delete the
folder and it is gone.

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
MARCO, which Microsoft provides for non-commercial research. The benchmark
files in `bench/` are not part of the software and quote the data they were
measured on under that data's terms (LoCoMo's are non-commercial); `NOTICE`
lists them.

## More

- Questions people ask (is this just RAG? what about Claude Code's memory?): [`docs/FAQ.md`](docs/FAQ.md)
- Every held-out set, run by run: [`docs/RESULTS_HISTORY.md`](docs/RESULTS_HISTORY.md)
- Full documentation: [`server/README.md`](server/README.md)
- What changed in each version: [`docs/CHANGELOG.md`](docs/CHANGELOG.md)
- Rerunning the benchmarks: [`bench/REPRODUCE.md`](bench/REPRODUCE.md)
- This repository also holds the research the product came from (`experiments/`, `notebook.md`).
