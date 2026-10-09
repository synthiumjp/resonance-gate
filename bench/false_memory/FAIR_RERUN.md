# The fair rerun (2026-10-09)

Done after the adversarial review (`docs/REVIEW_2026-10-09.md`, A1-A5)
found that the published head-to-head gave sourcedrecall's lines to the
reader with its own rules and every other system's lines bare, never
audited sourcedrecall's own release-run answers, judged answers without the
question, and matched expected terms as substrings.

What changed (`fair_run.sh`, commit 372c05a; options in `answer.py`,
`judge.py`, `score.py`):
- every system's saved returns went to the same reader (Qwen3-14B) with the
  same instruction: "Each memory line is something from earlier
  conversations, with its date where known. A later line can update an
  earlier one. If the memory does not answer the question, say you don't
  know." Variant A: sourcedrecall's block as an agent receives it (its own
  rules included). Variant B: sourcedrecall without its rules paragraph;
- the judge (the same model) saw the question with each answer;
- expected terms count only as whole words not already in the question;
  errors and missing answers count as failures;
- every answer to a forbidden claim was audited blind (`blind_audit.py`):
  the auditor (an AI agent) saw no system names, applied one rule to all,
  and overrode only clear judge errors. It added no false memories and
  removed some judge false alarms (most on control questions, which do not
  count as false memories): `audit_results_fair_*/decisions.jsonl`, keys in
  `audit_results_fair_*/key.json`;
- sourcedrecall was run fresh at this commit (with the review's fixes);
  the other systems' returns are those of the earlier runs, on the same
  cases.

## Results (answer view, audited; variant A, B where it differs)

| | sourcedrecall | agentmemory 0.9 | ai-memory 2.5 | plain retrieval | Mem0 2.2.1 |
|---|---|---|---|---|---|
| v4: old state given as current, of 44 | 2 | 4 (p=0.68) | 8 (p=0.09) | 5 (p=0.43) | |
| v4: new state given, of 44 | 42 (B: 40) | 38 (p=0.27) | 33 (p=0.01) | 36 (p=0.09) | |
| coding sessions behind 120 others: false memories, of 51 | 0 | 2 (p=0.50) | 5 (p=0.06) | 3 (p=0.24) | |
| several projects: false memories, of 32 | 0 | 8 (p=0.005) | 4 (p=0.11) | 3 (p=0.24) | |
| several projects: unchanged facts answered, of 13 | 11 | 11 | 6 | 6 | |
| v3: false memories, of 30 | 0 | | | 0 | 2 (p=0.49) |
| pooled v4 + coding + projects: false memories, of 127 | 2 | 14 (p=0.003) | 17 (p=0.0005) | 11 (p=0.02) | |

p: two-sided Fisher exact test against sourcedrecall (`fair_summary.py`).
Variants A and B gave the same false-memory counts on every set: the lead
does not come from sourcedrecall's instructions to the reader.

## What this does and does not show

Per set, only two differences are clear (projects against agentmemory; the
new state against ai-memory); pooled over the three sets all four systems
ran, sourcedrecall's 2 false memories in 127 against 11-17 for the others
are. The sets were written for this project, are synthetic and small, and
have been run many times during development (some rules were written from
their error categories), so they are not held out; the clean held-out set is
v5 (`results_v5/SUMMARY.md`). The reader and the judge are the same local
model. The other systems ran in the configuration they document for use
without a language model.
