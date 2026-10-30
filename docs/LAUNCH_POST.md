# Testers-wanted post (draft, 2026-10-29)

Not exported to the product repo. Figures checked against the README after
the 7a83a79 release run and the files it names (bench/native_memory;
docs/PREREG_CODING_V1.md).

## Long version (Reddit, forums)

Title: sourcedrecall: a record of your Claude Code sessions, beside Claude's own memory (looking for testers)

I've been building a memory plugin for Claude Code and I'm looking for
people to try it and tell me where it goes wrong.

Claude Code's memory is notes Claude writes for itself. sourcedrecall keeps
what those notes are written from: your messages in your own words with
their dates, and what each coding session did (the commands that failed,
what was changed after, whether it then passed, commits, the reasons
given). `/recall how did we fix the login test` searches past sessions and
answers with the date and session of each thing it uses. At the start of a
session it gives Claude a short summary, leaving out what the project's
MEMORY.md already says.

What's different about it:

- No language model writes or reads the memory. A grammar parser decides
  what is stored and what a later message replaced; the small models it
  uses (parser, search embedder, re-ranker, a contradiction check) run on
  your CPU. No API key; once installed, nothing leaves your machine.
- Text you paste in from someone else (an email, a review, a chat) is kept
  as theirs, not as something you said.
- Your memory is a folder of plain files. You can read it, correct it and
  forget single sentences.

How it measures, against a simulation of Claude Code's memory (Claude
Sonnet writing the memory folder session by session; the reader given the
whole folder): on 136 pre-registered questions about earlier sessions in 10
public repositories, the folder alone answered 56.6%, sourcedrecall 72.1%,
both together 80.9%. A plain search over the same session passages did
about as well as sourcedrecall alone (74.3%): the gain is from keeping the
sessions and searching them at all. On personal facts in long chats
(LoCoMo) Claude Code's memory is better, 76.6% against 65.6%; the two
together 81.9%. It is not better memory of you than Claude's own; it is the
record beside it. Everything, including where it loses, is in the repo with
the commands to rerun it.

What it doesn't do well yet: English only. A fact you change within the
same session is not marked as replaced until the session is stored. On
facts about other things that change (long lists of world facts), plain
retrieval does better. Pasted text whose source is named in ways its rules
don't read can still pass as yours. The Codex CLI, Gemini CLI and Cursor
hooks are included but not tested in those apps, and native Windows is
untested.

Install (Claude Code 2.1.83 or later, about 1.3 GB of disk):

    /plugin marketplace add synthiumjp/sourcedrecall
    /plugin install sourcedrecall@sourcedrecall

It asks for your name, then sets itself up in the background during your
first session. To check it works, start a new session and type
`! sourcedrecall-run memory status`. To bring in past sessions:
`! sourcedrecall-run import claude-code`.

What I'd like to hear: whether /recall finds what you were looking for,
anything it stored that you didn't say, anything it showed Claude that was
out of date, install problems (with your OS and Python version), and
whether the start-of-session summary helps or gets in the way. Issues on
GitHub, or reply here.

https://github.com/synthiumjp/sourcedrecall

## Short version (X, Bluesky, Discord)

sourcedrecall: a local record of your Claude Code sessions, beside Claude's
own memory. What you said in your words with dates, and what each session
did (failed commands, fixes, decisions), searchable with /recall. No LLM
writes it; it runs on your CPU. Looking for testers:
https://github.com/synthiumjp/sourcedrecall

## Show HN

Title: Show HN: sourcedrecall – a searchable record of your Claude Code sessions, written by a parser, not an LLM

Body: the first two paragraphs of the long version, the measurement
paragraph, the limits paragraph and the link.
