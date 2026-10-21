# Testers-wanted post (draft, 2026-10-21)

Not exported to the product repo. LoCoMo figures checked against the
012fcca release run (2026-10-22).

## Long version (Reddit, forums)

Title: sourcedrecall: local memory for Claude Code that keeps your own words (looking for testers)

I've been building a memory plugin for Claude Code and I'm looking for
people to try it and tell me where it goes wrong.

What it does: when you tell Claude something about yourself or your work,
sourcedrecall keeps the message as you wrote it, with its date. At the
start of a session, and when a question comes up, it hands Claude the few
messages that matter, oldest first, and marks what has changed since ("I
moved to Brunswick" after "I live in Fitzroy").

What's different about it:

- No language model writes or reads the memory. A grammar parser decides
  what is stored and what has gone out of date. The small models it uses
  (parser, search embedder, re-ranker, a contradiction check) run on your
  CPU. No API key; once installed, nothing leaves your machine.
- Text you paste in from someone else (an email, a review, a chat) is kept
  as theirs. Tools that store whatever was said will take a friend's "I'm
  allergic to nuts" for yours.
- Your memory is a folder of plain files on your machine. You can read it,
  correct it and forget single sentences.

How it measures: on LoCoMo, with the same local reader and judge for
every system, it answers about as many questions as Mem0 (65.6% against
64.6%) without any model call to store anything; with Claude Sonnet 5.5
reading, 77.0% against 72.1%. Its lead comes from questions about dates
and time; on the other questions Mem0 is ahead. Everything, including
where it loses, is in the repo with the commands to rerun it.

What it doesn't do well yet: English only. A fact you change within the
same session is not marked as replaced until the session is stored. Pasted
text whose source is named in ways its rules don't read can still pass as
yours. The Codex CLI, Gemini CLI and Cursor hooks are included but not
tested in those apps, and native Windows is untested.

Install (Claude Code 2.1.83 or later, about 1.3 GB of disk):

    /plugin marketplace add synthiumjp/sourcedrecall
    /plugin install sourcedrecall@sourcedrecall

It asks for your name, then sets itself up in the background during your
first session. To check it works, start a new session and type
`! sourcedrecall-run memory status`.

What I'd like to hear: anything it stored that you didn't say, anything
it missed, anything it showed Claude that was out of date, install
problems (with your OS and Python version), and whether the start-of-session
summary helps or gets in the way. Issues on GitHub, or reply here.

https://github.com/synthiumjp/sourcedrecall

## Short version (X, Bluesky, Discord)

sourcedrecall: local memory for Claude Code. It keeps what you tell Claude
in your own words, with dates, and marks what has changed. A grammar
parser writes the memory, not an LLM; it runs on your CPU with no API key.
Pasted emails and chats stay someone else's. Looking for testers:
https://github.com/synthiumjp/sourcedrecall

## Show HN

Title: Show HN: sourcedrecall – Claude Code memory written by a grammar parser, not an LLM

Body: the first three paragraphs of the long version, the LoCoMo paragraph,
the limits paragraph and the link.
