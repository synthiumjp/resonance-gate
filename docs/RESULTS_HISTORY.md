# Held-out sets, run by run

Each set below was written for this project, pre-registered (hypotheses
fixed before the set existed), read by nobody working on the system, and
run once when it was new. Each paragraph reports that run; the paragraph
after it says what was changed before the next set. Rules added after v12
were built from the kinds of text v12 missed, so v11, v12 and the real
emails are no longer unseen for later code; their counts on later commits
are in the README and the release logs (`bench/RELEASE_*.log`).

A pre-registered held-out set (v5: 120 scenarios nobody working on the
system had read, hypotheses fixed beforehand, run once): old state given as
current in 0 of 25 stated changes and 3 of 25 implied ones (plain retrieval
4 and 7; neither difference is significant), decisions recalled 10 of 10, no
declined proposal given as decided. Two hypotheses missed (the labels on
implied changes, and "no longer true" against its base rate). The one clear
difference went against sourcedrecall: asked for advice, its reader used
what the user had mentioned in 2 of 10 answers, plain retrieval's in 8 of 10
(p=0.02). Everything is in `bench/false_memory/results_v5/SUMMARY.md`.

A second pre-registered held-out set (v6: 140 scenarios, run once on
2026-10-09 under the protocol above, against all four systems) tested the
fixes made after an adversarial review. Four of eight hypotheses met: a
change that happened, old state given as current 0 of 20; hedged or
reported claims given as fact 1 of 14; in long coding sessions the
instruction or decision in force recalled 23 of 25 and a reversed one given
as current 0 of 8; standing instructions shown at the start of a session
for 11 of 12, and none of 3 idioms. Four missed. Pasted text: a claim or
instruction inside pasted material was given as the user's own in 14 of 17
(plain retrieval and agentmemory 15, ai-memory 3, which keeps only the
first line of a message); the "pasted in" marker fired on 3 of the 14, and
the reader ignored it on those too. Because of this, sourcedrecall had no
fewer false memories than the other systems on v6 (15 of 59, against 17,
17 and 10; 14 of its 15 are pasted text). Advice: the earlier mention was
used in 3 of 15 answers (plain retrieval 2); in every miss the reader said
it did not know, following the shared instruction to do so. A plan
mentioned later was taken to mean the earlier state had ended in 4 of 20
(others 4 to 6). Everything is in `bench/false_memory/results_v6/SUMMARY.md`.

Pasted text was then changed (whose text it is read from the introduction,
the writer named in the block, the rules no longer calling quoted text the
user's) and tested on a third pre-registered held-out set (v7: 140
scenarios, run once on 2026-10-10, all four systems). A claim or instruction
inside pasted material was given as the user's in 11 of 34 (32%, from 82%
on v6), against plain retrieval's 24 and agentmemory's 26 (both p<0.01);
ai-memory 2, again by keeping only first lines (it answered 4 of 16 of the
user's own pasted material). Where the "pasted in" marker fired the reader
almost never took the text for the user's; the 10 it missed had
introductions worded in ways the rules do not cover. Old state given as
current 0 of 20. Advice: the earlier mention used in 11 of 20 (plain
retrieval 7), none of 10 irrelevant mentions applied. Five of seven
hypotheses missed, including the 4-of-34 target for pasted text; in the
advice, plan and everyday parts most misses were the reader saying it did
not know with the answer in front of it. Everything is in
`bench/false_memory/results_v7/SUMMARY.md`.

Detection was then changed to read a message's shape (a short line of the
user's and a block in another voice, the introduction before or after it)
and tested on a fourth held-out set (v8: 100 scenarios, 2026-10-10). Pasted
claims or instructions given as the user's: 9 of 40 (22%; plain retrieval
16, agentmemory 20, ai-memory 2), so across v6, v7 and v8: 82%, 32%, 22%.
The pre-registered target of at most 6 of 40 was missed, and the difference from plain
retrieval was not significant (p=0.15) on this set, where pasted text misled
every system less. The marker fired on 24 of the 40; 4 marked items were
still given as the user's, 3 of them pasted instructions the reader
followed. Changes and everyday facts held (old state given as current 2 of
20, facts answered 18 of 20). Everything is in
`bench/false_memory/results_v8/SUMMARY.md`.

After v8, the writer's sentences about themselves and their general rules
were left out of pasted text unless the question names where it came from,
and long messages were cut around the question. A fifth held-out set (v9:
120 scenarios, 2026-10-11) met four of six hypotheses. Pasted claims or
instructions given as the user's: 4 of 40 (10%; plain retrieval 22,
agentmemory 27, ai-memory 3; p<0.001 against the first two), so across v6
to v9: 82%, 32%, 22%, 10%. Pooled false memories 6 of 60 (plain retrieval
24, agentmemory 29, ai-memory 6). Changes and everyday facts held (2 of 20, 16 of 20).
Two targets were missed, both costs of these changes. The user's own
material was answered in 12 of 20 (target 15; plain retrieval 17): in 4,
own text was taken for pasted and the fact was left out. Facts asked about
inside pasted text were answered in 13 of 20 (target 16; plain retrieval
20): in all 7 misses the paste was over 800 characters and the part shown
did not hold the fact. Everything is in
`bench/false_memory/results_v9/SUMMARY.md`.

After v9, pasted text and long messages were shown in longer windows cut
around the question, the writer's details were left out only for questions
about you, and your own text was recognised by how you introduce or sign
it. A sixth held-out set (v10: 120 scenarios, 2026-10-11) met five of six
hypotheses. Pasted claims or instructions given as the user's: 3 of 40 (8%;
plain retrieval 23, agentmemory 20, ai-memory 0; p<0.001 against the first
two). Facts inside pasted text were answered in 17 of 20 (plain retrieval
20, agentmemory 8), 11 of the 12 long pastes among them. Pooled false
memories 4 of 60 (plain retrieval 26, agentmemory 20, ai-memory 7); changes 1 of 20,
everyday facts 18 of 20. The miss: the user's own material was answered in
13 of 20 (target 15; plain retrieval 19). In 6 of the 7 misses the fact was
in what the reader was given and it said it did not know. A refusal is
never counted as a false memory, so read the false-memory counts with how
often each reader said it did not know: on the 40 pasted claims (where that
is the right answer) sourcedrecall 35, plain retrieval 15, agentmemory 17,
ai-memory 40; on the 20 own items (where it is wrong) 7, 1, 3 and 17.
Everything is in `bench/false_memory/results_v10/SUMMARY.md`.

After v10, other messages were shown beside the one a question is about
only when they are close to the question, and more introductions were read
("sent me", "written by", "from my boss"). A seventh held-out set (v11: 130
scenarios, 2026-10-13) was read by two readers of different model families,
Qwen3-14B and Phi-4, and met seven of eight hypotheses with the first.
Pasted claims or instructions given as the user's: 5 of 40 (plain retrieval
23, agentmemory 24, ai-memory 2; Holm-adjusted p<0.001 against the first
two); with Phi-4 5 of 40 (22, 22, 3). Facts inside pasted text 20 of 20,
changes 0 of 20, everyday facts 17 of 20. The user's own material was
answered in 24 of 30 with both readers (target 23), but 6 behind plain
retrieval (target: at most 3 behind): in all 6 the user's own writing
(a diary entry, a speech, a blog draft, two statements and a sale ad) was
taken for someone else's and its facts left out, in 5 of them although the
user had called it theirs. Without the rules paragraph the counts were the
same, so they come from what the memory returns, not from the instruction.
Said it did not know: on the 40 pasted claims sourcedrecall 31, plain
retrieval 16, agentmemory 14, ai-memory 38; on the 30 own items 6, 0, 0
and 25. Everything is in `bench/false_memory/results_v11/SUMMARY.md`.

After v11, the user's own writing brought to be read over ("my blog post",
"I write it every month") was kept as theirs, letter-shaped text was read
as someone else's, and an email pasted on its own was read with the
user's next message ("it's from a client"). An eighth held-out set (v12:
160 scenarios, 2026-10-13), with a new part of 30 real emails from the
public Enron corpus, met seven of eleven hypotheses with Qwen3-14B.
Pasted claims or instructions given as the user's: 12 of 40 (target 6;
plain retrieval 28, agentmemory 35, ai-memory 8; Holm-adjusted p 0.002 and
below 0.001 against the first two); with Phi-4 13 of 40 (32, 35, 9). Real
emails: 7 of 20 (target 6; plain retrieval 14, p=0.06); the user's own
real emails answered 10 of 10. Own material 25 of 30 (target met; 4 behind
plain retrieval, target at most 3). Facts in pasted text 19 of 20, changes
1 of 20, everyday 19 of 20. The detection itself did no worse than v11's
code on this set; a third of the pasted texts came in shapes its rules do
not read (the source named in other words, after the text, or only in a
later message), and were taken for the user's. Everything is in
`bench/false_memory/results_v12/SUMMARY.md`.

After v12, a third person named around a first-person block ("my brother,
last night:") marks it as theirs, and a small learned model judges what the
rules leave unmarked. Both were developed on a new set written from the
kinds of text v12 missed (categories only, not its items), so v11, v12 and
the real emails are no longer unseen for this code. Run again on the
release commit (012fcca), counts only: pasted claims or instructions given
as the user's 3 of 40 on v11 and 8 of 40 on v12 with Qwen3-14B (plain
retrieval 23 and 28, agentmemory 24 and 35, ai-memory 2 and 8), 3 and 10
with Phi-4; v12's 20 real emails 5 of 20 with Qwen3-14B and 4 with Phi-4
(plain retrieval 14 and 14); the separate held-out set of 20 real pasted
emails (`cases_real_paste.jsonl`, first run end to end on 1d92020: 7 and 5
of 20, plain retrieval 15 and 16) 1 of 20 with both readers (plain
retrieval 16 and 17). Own material 25 of 30 on both sets with Qwen3-14B
(plain retrieval 30 and 29). With Claude Sonnet 5.5 reading the returns of
53e0d9c (judged by Qwen3-14B, no audit): pasted claims given as the user's
0 of 40 on both sets (plain retrieval 0 and 2, agentmemory 1 and 3,
ai-memory 1 and 4), v12's real emails 0 of 20 (plain retrieval 1), the
separate real-email set 0 of 20 (plain retrieval 5), own material 25 and 26
of 30 (plain retrieval 30 and 30). A strong reader mostly tells pasted text
from the user's own on its own; what sourcedrecall marks matters most with
smaller models (`bench/false_memory/results_release2_*`, `results_claude_*`).

On commit 3671a09 (2026-10-28, after the review fixes and the updated-facts
change) the counts are the same except v12's real emails with Phi-4 (5 of
20) and the separate real-email set's own emails (8 of 10, was 9);
`bench/RELEASE_3671a09.log`.
