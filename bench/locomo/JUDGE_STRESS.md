# How lenient is the LoCoMo judge?

`judge_stress.py`, local Qwen3-14B as the judge, test conversations 2-9.
The wrong answers are the LoCoMo audit's (github.com/dial481/locomo-audit,
fetched by `fetch_audit.sh`): v1 specific but wrong, v2 vague but on topic.

| | usual prompt | strict prompt (`LOCOMO_JUDGE=strict`) |
|---|---|---|
| v1 wrong answers accepted | 137 of 1,296 (10.6%) | 12 of 400 (3.0%) |
| v2 wrong answers accepted | 888 of 1,296 (68.5%) | 80 of 400 (20.0%) |
| gold answers accepted, a random 120 | | 120 of 120 |

The audit reports 10.6% and 62.8% for gpt-4o-mini with the usual prompt.
The wrong-answer runs (2026-10-10) kept only these counts here, since their
answers are the audit's; the gold check (2026-10-14) is
`results/judge_gold_strict.jsonl`.
