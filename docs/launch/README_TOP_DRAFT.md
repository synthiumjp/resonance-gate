# Draft: the README's opening (2026-10-12, for JP's review)

Follows the launch review: lead with what no other memory measures, state
the costs in the same breath, numbers from one run each. Bracketed items
are filled from the v11 run and the external benchmarks before it replaces
the current opening.

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
friend's "I'm allergic to nuts" for yours. On a pre-registered held-out
set, plain retrieval gave 23 of 40 pasted claims back as the user's own,
agentmemory 20, and sourcedrecall 3 [v11: _ of 40]. The cost: on the
user's own pasted-shaped material it answered 13 of 20 where plain
retrieval answered 19 [v11: _ of 30 against _], and its reader more often
said it did not know.

On LoCoMo, with the same local reader and judge for every system, it is
level with Mem0 (49.7% against 48.5% with a strict judge; 65.3% against
64.6% with the benchmark's usual judge) while making no model call to
store anything; Mem0 is ahead on questions that combine several facts.
[External: HaluMem / LongMemEval knowledge-update, if the overnight runs
show a clear result.]

Everything is in `bench/`, with the commands to rerun it. English only.
