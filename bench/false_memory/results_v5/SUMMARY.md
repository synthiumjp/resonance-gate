# Held-out set v5: results

Pre-registered in `docs/PREREG_HELDOUT_V5.md` (reviewed by JP and committed
before the set existed, 43b38c2 and d1c4847). The set (`cases_v5.jsonl`, 120
scenarios) was written by an agent from a brief without the rules' word
lists and has not been read by the developer. One run on commit 11d2446 (no
system code changed since the pre-registration), 2026-10-08: local Qwen3-14B
reader and judge, answer view, audited by an agent with one rule for both
systems (2 overrides, one per system, both on the same scenario where the
judge flagged an answer that gave the new state). Plain retrieval: the top 3
user messages by bge-small.

| | hypothesis | sourcedrecall | plain retrieval | |
|---|---|---|---|---|
| H1 | changes stated: old state given as current, at most 2/25 | 0/25 | 4/25 | met |
| H2a | changes implied: old state given as current, at most 6/25 | 3/25 | 7/25 | met |
| H2b | changes implied: "may have changed since" or "no longer true" on at least 12 of the 25 out-of-date lines | 1 of the 15 lines `screen_labels.py` could match (the audit: 2 of 25 scenarios labelled correctly) | | missed |
| H3 | no change: a change label on a current fact, at most 1/20 | 0/20 ("said in passing" once) | | met |
| H4 | decisions: accepted recalled at least 7/10; declined given as decided at most 1 | 10/10; 0/10 | 9/10; 0/10 | met |
| H5 | claim check: "said" for a denied, hedged, assistant-only or never-said claim, at most 2 | 1 of 12 | | met |
| H6 | advice: the answer's conversation in the top 5, at least 8/10 | 10/10 | | met |
| H7 | every label family above its unlabelled base rate (`screen_labels.py`) | "no longer true" 0/4 against 4.9% | | missed |

Other parts, answer view: no change (C), the current state answered 20/20
(plain retrieval 17/20); true claims (E) 4/4 for both; false claims (E,
classes a, c, e) 0/12 false memories for both.

## What the audit found behind the misses (categories, counts)

- H2b. In all 25 implied-change scenarios both the out-of-date fact and the
  newer message were in the memory block. The label was on the out-of-date
  fact in 2, on an unrelated line in 1, and absent in 22: in 10 the newer
  message says the old state ended in its own words ("former", "used to",
  "moved out of"), in 12 it only states a new state. The answers were right
  in 22 of 25: the dated quotes, not the labels, carried them.
- H7. Of the 4 "no longer true" lines, 3 mark the right out-of-date fact and
  1 marks a past event rather than a standing state; none is about an
  unrelated fact. `screen_labels.py` counts a line as about the out-of-date
  state only if it shares the probe's words, and these were phrased as
  events. As measured, the hypothesis is missed.
- Not a hypothesis: for advice requests (F) the earlier mention was in
  sourcedrecall's block in 10 of 10, yet the reader's answer contained the
  expected item in 2 of 10 (plain retrieval 8 of 10): it ignored the mention
  and recommended something generic (4), paraphrased it (2), or said it had
  no recommendation (2).

Any fix for these is measured on a different set.
