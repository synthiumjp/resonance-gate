# Pre-registration: coding recall v1 (approved by JP 2026-10-22)

JP approved this design on 2026-10-22 evening, with the history at 40
sessions. The question writer, the extractor and retrieval may still change
on dev; the file is committed as frozen, with the writer prompt and the code
commit, before any held-out session is fetched. Nothing in "Held out" is
read, tuned on or looked at before then. Plan: docs/PLAN_GAPS_2026-10-22.md, G1.

Dev log:
- 2026-10-22: first dev question set (107 questions) failed the 30-question
  check, 8 of 30 by a blinded Sonnet reviewer (vague: "the test", "the
  article"; generated file names; absolute paths). The writer prompt now
  asks for the specific thing by name, one possible answer, repository
  paths, no generated names, and "where" as where a change was made. The
  question set is rewritten and the check repeated.
- 2026-10-23: the rewritten set (111) failed again, 9 of 30 (trivial "which
  file was modified" questions whose answer repeats the question; one copied
  the prompt's example). A Qwen vetting pass agreed with the reviewer on 1 of
  the 9. A Sonnet subagent then vetted all 111 with the question, gold and
  evidence (never any system's output), on the reviewer's criteria: 53 kept
  (fix 21, how 16, where 13, why 3). A fresh blinded Sonnet reviewer on 30 of
  the 53: 5 fail, at the limit.

- 2026-10-23, dev scores (Qwen reader, 111 questions / the 53 vetted):
  records only: sourcedrecall 30 / 14, native-qwen 26 / 12, both 40 / 23,
  rag 75 / 41. With session excerpts (61a1164): sourcedrecall 67 / 35
  (2,493 context tokens), both 66 / 37, native-qwen 26 / 12 (7,545), rag
  75 / 41 (2,581); ours vs rag 5 to 13, p=0.10; ours vs native 46 to 5.

Proposed for held out (needs JP's review): the Sonnet vet as a step of the
question protocol, after the automatic drops; 12 question sessions per
repository instead of 6, since about half the questions survive the vet
(about 200 held-out questions); the 30-question check by JP on the
vetted held-out set, as a vet and a check by the same model family are not
independent.

## Question

After a run of real coding sessions on one project, can the memory answer
what a developer on that project asks later: what failed and what fixed it,
how things are run, why something was decided, where a change was made?
And does sourcedrecall add to native memory (Claude Code's own), or not?

## Data

SWE-chat v2 (SALT-NLP/SWE-chat, revision df393df, ODC-By; Baumann et al.,
COLM 2026): real developer sessions from public repositories, with tool
calls. Eligible: Claude Code sessions, not marked delta-only, at least 10
tool calls; repositories with at least 20 such sessions, a permissive
licence, not entireio/cli (28 users, 2,099 sessions). 89 repositories.
Sorted by sha256("coding-v1:" + repo id): the first 10 are dev, the next 20
held out (bench/coding/split_v1.json, sha256 65787c69...). Transcripts,
questions and answers stay on the Mac and are not committed; results are
counts.

Second set (JP agreed 2026-10-22): JP's own Claude Code sessions, same
protocol, on the Mac only, counts only, never committed or quoted.

## History and questions

Per repository, the history is its eligible sessions in time order, at most
the first 40. Questions are asked as if at the start of the session after
the history.

Questions are written by Qwen3-14B from one history session at a time
(6 sessions per repository, spread evenly over the history), from a
condensed transcript: what the user typed, the assistant's text, each tool
call with its command or file and the first 300 characters of its result.
Up to 3 per session, each of one type:

- fix: what went wrong with something and what fixed it (or that it was
  not fixed)
- how: how something is run, built, tested or deployed in this project
- why: why something was done or chosen, or what was ruled out
- where: which file or component holds or changed something

Each comes with a short gold answer and an evidence quote. Dropped
automatically: evidence not found verbatim in the condensed transcript;
questions Qwen3-14B answers correctly with no memory at all (general
knowledge); near-duplicates. The question writer never sees any system's
memory. Before the held-out run, JP or a blinded reviewer reads 30 random
dev questions; if more than 5 are not questions a developer would ask,
the writer prompt is fixed on dev and the check repeated.

## Systems

All get the same reader prompt and a context budget reported per question.

1. sourcedrecall: what Claude would get for the question: the top 8
   coding records (history_search) and the top 4 of the user's messages
   (profile_context).
2. native memory, simulated with Qwen3-14B as the writer
   (bench/claude_memory.py's instructions, run after each session on the
   condensed transcript). Labelled: Claude Code's memory is written by
   Claude, so this is unfair to it. The Sonnet 5.5 writer is run as the
   main comparison when API credit is back (about 3 weeks), unchanged.
3. native memory and sourcedrecall together (both contexts).
4. plain retrieval: the top 10 chunks of the condensed transcripts (same
   embedder), the baseline any memory must beat.

## Reading and judging

Reader Qwen3-14B (temperature 0), Phi-4 as second reader. Judge Qwen3-14B
with the question, gold answer and evidence, strict prompt (the answer must
state the gold's specific content; "I don't know" is wrong). A blinded
audit of 60 judged answers per system on held out, as for the pasted-text
sets.

## Gates (decided now)

- Main: native + sourcedrecall answers at least 10 points more than native
  alone on held out, paired McNemar p < 0.05, with the Qwen reader.
- sourcedrecall alone at least matches native alone on fix questions.
- sourcedrecall alone at least matches plain retrieval overall (else the
  records add nothing over searching the transcripts, and the README says
  so).
- Reported whatever the outcome, per type, both readers, with context size.

If the main gate fails, launch stays held; the result is written up and
the next step decided with JP.
