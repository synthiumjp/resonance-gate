# Held-out real emails (cases_real_paste): end to end

`cases_real_paste.jsonl`: 30 scenarios built on real emails from the public
Enron corpus (Yale-LILY/aeslc; bodies verbatim, digits lightly altered), 20
pasted in with a first-person claim of the writer's and 10 the user's own;
framing by a sonnet agent; held out, read by the developer as counts only.
Not pre-registered: built to check whether pasted-text detection tuned on
agent-written sets carries over to real writing (review 2026-10-12, 2.4).

Measured once end to end, on 1d92020 (the merge of the post-v11 fixes),
2026-10-13, under the v7 protocol (every system's returns to the same
reader with the same instruction, the judge Qwen3-14B given the question,
strict scoring); no audit. sourcedrecall and plain retrieval only.

| | Qwen3-14B reader | Phi-4 reader |
|---|---|---|
| a real writer's claim given as the user's (20): sourcedrecall | 7 | 5 |
| the same, plain retrieval | 15 (p=0.02) | 16 (p<0.01) |
| the user's own email, fact answered (10): sourcedrecall | 9 | 9 |
| the same, plain retrieval | 10 | 10 |

Detection alone on this set (no model): marked as pasted 7 of 20 before the
letter rule (post-v11 code), 12 of 20 after it, own kept 10 of 10. On the
readable development set of real emails (`cases_dev_real.jsonl`) the same
code gives 4 of 30 claims taken as the user's with Qwen3-14B (frozen v11
code 18) and 6 with Phi-4 (19). So about a third of real pasted emails
still pass for the user's own on unseen mail, against three quarters with
plain retrieval: the rules carry over in part, and the gap from the
development set (4/30) is the part fitted to the emails read.

Files: `results_realpaste/` (Qwen3-14B) and `results_realpaste_phi4/`; the
Mac home directory written as `~/`.
