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

The last point is where plain retrieval goes wrong most. On a held-out set
of 40 pasted claims (pre-registered, `bench/false_memory/results_v10/`),
plain retrieval over the same messages gave 23 of them back as the user's
own; sourcedrecall gave 3. Its reader also said "I don't know" more often
(35 of the 40, where that is the right answer, against 15), and on the
user's own material answered less often (13 of 20, against 19): both are
in the README.

## Claude Code already has memory. Why add this?

Claude Code's auto memory is notes that Claude writes for itself, kept per
project, and only in Claude Code. sourcedrecall keeps what you said, with
dates, works the same in Claude Code, Codex CLI, Gemini CLI,
Cursor and any MCP client, and marks what has gone out of date. We have not
measured the two side by side.

## Does it use a language model?

Not to store anything. A grammar parser (Stanza's English models, run on
ONNX Runtime) reads your messages; small embedding and ranking models find
the relevant ones. Optional notes can be written by a small local model
that runs in the process, or by your own model server.

## Which model reads the memory?

Whichever your agent uses. The memory is text with a short paragraph of
rules. It was measured with two local model families (Qwen3-14B and
Phi-4); on the development sets both used it well.

## How much context does it add?

On LoCoMo, about 1,000 tokens a question on average (8 lines by default in
the product, 5 in the benchmark). `sourcedrecall-memory last` shows the
last block your agent was given and its size.

## Is anything sent anywhere?

No. The models run on your machine and the server works offline after
setup. The memory is a folder of plain files in `~/.sourcedrecall`.

## How do I see or remove what it stored?

`sourcedrecall-memory show` (or `MEMORY.md`, or the read-only browser with
`sourcedrecall-memory view`) lists everything with an id;
`sourcedrecall-memory forget <id>` erases the sentence it came from.
Deleting the folder deletes the memory.

## What languages does it read?

English. Other languages are stored and searched, but the parser does not
read them, so nothing is marked out of date and pasted text is not told
apart.

## How good is it, honestly?

Level with Mem0 on the LoCoMo benchmark with the same local reader and
judge (65.3% against 64.6%, 49.7% against 48.5% with a strict judge), with
no model call to store anything; behind Mem0 on questions that combine
several facts. Far fewer pasted claims taken for yours. The test sets for
false memories were written by a language model for this project, held out
and pre-registered; they are not a public benchmark. Everything is in
`bench/`.
