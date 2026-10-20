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
sourcedrecall is not yet reliable. On the two newest held-out sets of 40
pasted claims (pre-registered, `bench/false_memory/results_v11/` and
`results_v12/`), plain retrieval over the same messages gave 23 and 28 of
them back as the user's own; sourcedrecall gave 5 and 12, about the same
with a second reader model. On 20 real pasted emails: 7 against 14
(p=0.06). Since then those sets have been used to make new rules, so they
are no longer unseen. Its
reader also says "I don't know" more often, and on the user's own writing
answers a little less often (25 of 30 against 29): all in the README.

## Claude Code already has memory. Why add this?

Claude Code's auto memory is notes that Claude writes for itself, kept per
project, and only in Claude Code. sourcedrecall keeps what you said, with
dates, and marks what has gone out of date. It stores Claude Code sessions
automatically, and its tools work in any MCP client; hooks for Codex CLI,
Gemini CLI and Cursor are included but not yet tested in those apps. We have not
measured the two side by side.

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
Phi-4); on the development sets both used it well.

## How much context does it add?

On LoCoMo, 682 tokens a question on average, about 13 messages (the
benchmark run asks for 5 lines per speaker; the product's default is 8, so
a little more). With the notes model, about 1,000. `sourcedrecall-memory last` shows the
last block your agent was given and its size.

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
so on, or ask Claude to forget something.
Deleting the folder deletes the memory.

## What languages does it read?

English. Other languages are stored and searched, but the parser does not
read them, so nothing is marked out of date and pasted text is not told
apart.

## How good is it?

On LoCoMo, with the same local reader and judge, about as many answers as
Mem0 (65.4% against 64.6%, p=0.61; 50.9% against 48.5% with a strict
judge), and more with Claude Sonnet 5.5 reading and judging (77.0% against
72.1%), with no model call to store anything. Both leads come from
questions about dates, where Mem0 was at a disadvantage (it takes no
timestamp); on the other questions Mem0 is ahead (71.3% against 67.5%, and
81.5% against 77.6% with Claude). With a local model as the reader, far
fewer pasted claims are taken for yours; a strong hosted reader such as
Claude mostly tells pasted text apart by itself. The false-memory test
sets were written by a language model for this project and are not a
public benchmark; some were held out and pre-registered, and the newest of
those have since been used to make rules, so they are no longer unseen.
Everything is in `bench/`.
