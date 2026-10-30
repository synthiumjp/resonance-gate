# Questions people ask

## Isn't this just retrieval (RAG) over my chats?

Partly, yes: when a question comes in, it finds your earlier messages and
hands them to the agent. The difference is in what is kept and how it is
shown:

- your own words, dated, oldest first; nothing is rewritten when it is
  stored, so there is no summary for a model to get wrong;
- a statement that a later one replaced is marked "no longer true", and one
  that may have changed is marked as such, by a grammar parser that reads
  changes of state ("I moved to", "I started at", "we switched back to");
- text you paste in from someone else (an email, a review, a chat) is shown
  as theirs, with the writer named, not as something you said.

The last point is where plain retrieval goes wrong most, and where
sourcedrecall is not yet reliable. On the two newest pre-registered
held-out sets of 40 pasted claims, plain retrieval over the same messages
gave 23 and 28 of them back as the user's own when the sets were new;
sourcedrecall gave 5 and 12, about the same with a second reader model, and
3 and 8 on the current code, which was partly built from those sets' misses.
On 20 real pasted emails: 5 against 14. Its reader also says "I don't know"
more often, and on the user's own writing answers a little less often (25
of 30 against 29 or 30).

On coding history the search itself is close to plain retrieval: over the
same session passages, a plain embedding search answered as many questions
(101 of 136 against 98). What sourcedrecall adds there is that the sessions
are kept, split into passages and searched at all.

## Claude Code already has memory. Why add this?

Claude Code's memory is notes Claude writes for itself, kept per project.
sourcedrecall keeps the record those notes are written from: your messages
with their dates, and what each coding session did (commands, failures,
fixes, decisions). We measured the two side by side, with Claude Code's
memory simulated by Claude Sonnet 5.5 following its published guidance
(`bench/native_memory/`):

- on questions about past coding sessions, the memory folder answered
  56.6%, sourcedrecall 72.1%, both together 80.9%;
- on personal facts in long chats (LoCoMo), Claude Code's memory is better:
  76.6% against 65.6% (with Claude reading, 86.5% against 77.2%); both
  together 81.9%;
- on pasted text, Claude's notes rarely took a pasted claim for the user's
  (about as rarely as sourcedrecall), but lost more of the detail inside it.

So it is meant to run beside Claude Code's memory: the session-start
summary leaves out what the project's `MEMORY.md` already says. Its tools
also work in any MCP client; hooks for Codex CLI, Gemini CLI and Cursor are
included but not yet tested in those apps.

## Does it use a language model?

No language model writes or reads the memory. A grammar parser (Stanza's
architecture, trained on the UD English-EWT treebank, run on ONNX Runtime)
reads your messages; small embedding and ranking models find the relevant
ones; a small model checks whether two stored values contradict each
other; and a small classifier helps tell pasted text from yours. All of
them run on your CPU. Optional notes can be written by a small local model
that runs in the process, or by your own model server.

## Which model reads the memory?

Whichever your agent uses. The memory is text with a short paragraph of
rules. It was measured with two local model families (Qwen3-14B and
Phi-4) and, on some sets, Claude Sonnet 5.5.

## How much context does it add?

On LoCoMo, 651 tokens a question on average, about 13 messages (the
benchmark run asks for 5 lines per speaker; the product's default is 8, so
a little more). With the notes model, about 1,000. A coding-history search
returns 10 passages, about 2,700 tokens. `sourcedrecall-memory last` shows
the last block your agent was given and its size.

## Is anything sent anywhere?

Not by sourcedrecall. The models run on your machine and the server works
offline after setup, which downloads the Python packages and the models
once. What it gives your agent goes to your agent's model like any other
context, so with a hosted model it leaves your machine with the rest of the
conversation. The memory is a folder of plain files in `~/.sourcedrecall`.

## How do I see or remove what it stored?

`sourcedrecall-memory show` (or `MEMORY.md`, or the read-only browser with
`sourcedrecall-memory view`) lists everything with an id;
`sourcedrecall-memory forget <id>` erases the sentence it came from. With
the Claude Code plugin, type them as `! sourcedrecall-run memory show` and
so on, or ask Claude to forget something. Deleting the folder deletes the
memory.

## What languages does it read?

English. Other languages are stored and searched, but the parser does not
read them, so nothing is marked out of date and pasted text is not told
apart.

## How good is it?

On LoCoMo, with the same local reader and judge, about as many answers as
Mem0 (65.6% against 64.6%, p=0.54), and more with Claude Sonnet 5.5 reading
and judging (77.0% against 72.1%), with no language-model call to store
anything. Both leads come from questions about dates, where Mem0 was at a
disadvantage (it takes no timestamp); on the other questions Mem0 is ahead
(71.3% against 68.0%, and 81.5% against 77.6% with Claude). Claude Code's
own memory, simulated, is ahead of both on LoCoMo. On facts about other
things that change (MemoryAgentBench), plain retrieval is ahead. With a
local model as the reader, far fewer pasted claims are taken for yours; a
strong hosted reader such as Claude mostly tells pasted text apart by
itself. The false-memory and coding test sets were written by language
models for this project and are not public benchmarks; the held-out ones
were pre-registered, and the newest pasted-text sets have since been used
to make rules, so they are no longer unseen. Everything is in `bench/`.
