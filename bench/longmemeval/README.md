# LongMemEval-S retrieval recall

Does the memory find the conversation that holds the answer? LongMemEval-S
([xiaowu0162/LongMemEval](https://github.com/xiaowu0162/LongMemEval), MIT)
gives each of 500 questions a history of about 50 chat sessions and labels
the sessions that hold the evidence. No language model is involved here:
this measures retrieval only, the number other memory tools publish for
this benchmark.

Run at commit 1754180 (2026-10-07, the release run; first run e8b8c0f, 98.4%) on a Mac, `longmemeval_s_cleaned.json`
from huggingface.co/datasets/xiaowu0162/longmemeval-cleaned.

## Result

Session-level recall_any@5 (a gold session among the top 5), all 500
questions, the set and metric agentmemory and MemPalace report:

| | recall_any@5 | recall_all@5 | recall_any@10 |
|---|---|---|---|
| sourcedrecall (message search) | 98.8% | 92.6% | 99.2% |
| bge-small embeddings, same index | 96.8% | 89.8% | 98.4% |
| BM25, same index | 93.4% | 77.6% | 96.2% |
| agentmemory, as published | 95.2% | | |
| MemPalace, as published | 96.6% | | |

Without the 30 abstention questions (the official retrieval set, n=470):
any@5 98.7%, all@5 93.4%. Per question type, k=1 to 10, and turn-level
figures are in `release_report.md` (first run: `report.md`).
Single-session-preference, the weakest type in the first run (any@5 90.0%,
plain embeddings 96.7%), is 96.7% since requests for advice are ranked by
embeddings; that routing was chosen on those 30 questions.

## What was measured, exactly

- Each question gets a fresh store. Every haystack session is stored with
  `profile_ingest`, dated with its haystack date.
- The ranking is `profile_memory._messages_for(question, k=50)`: the
  product's message search (BM25 and bge-small candidates, re-ranked by the
  ms-marco MiniLM cross-encoder) over the user's messages. Sessions are
  ranked by first appearance among the returned messages.
- The parser was replaced by a stub during ingest (`FULL=1` keeps it). The
  message search reads only the stored conversations, so the parser cannot
  change this ranking; on the two questions run both ways the rankings were
  identical. With the parser, ingest took about two minutes per question.
- Only user messages are indexed, as in the product. Other tools' set-ups
  differ (agentmemory's benchmark script indexes both sides of each session;
  see their repositories); the figures quoted for them are as they publish
  them.
- agentmemory's 95.2% is over all 500 questions (its per-type counts in
  benchmark/LONGMEMEVAL.md add up to 500), so the comparison above uses the
  same 500.
- The two baselines use the same index (messages of three words or more).

`run.py` writes one line per question (`results.jsonl`: ranked sessions and
turns); `report.py` computes the tables. The results also carry a column
from an option (`RG_FUSE`) that was tested on LoCoMo and not adopted; it is
not reported.

## Preference questions, answer level (2026-10-08)

`pref_answers.py`: each of the 30 single-session-preference questions is
stored, sourcedrecall builds its block, the local Qwen3-14B answers, and the
same model judges the answer against the question's own description of what
the user would prefer. With the advice handling (commit 632d83a) 16/30,
without it 13/30 (+5/-2): `pref_answers_on.jsonl`, `pref_answers_off.jsonl`.
