# Draft: the README's opening (2026-10-12, for JP's review)

Follows the launch review: lead with what no other memory measures, state
the costs in the same breath, numbers from one run each. Bracketed items
are filled from the v11 run and the external benchmarks before it replaces
the current opening. v11 and v12 filled 2026-10-13 (results_v11, results_v12);
the strict LoCoMo figure is the d89d830 re-judge (night chain); LongMemEval
knowledge-update, install size and speed added 2026-10-13 (notebook e331).

---

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
