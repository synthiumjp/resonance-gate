# LongMemEval-S retrieval recall
- 2026-10-05 dataset: longmemeval_s_cleaned.json (500 q, 30 abstention)
- Full ingest with the stanza fact parser measured 110-125 s/question (53 sessions, ~250 user msgs): ~17 h for 500. Message search reads only conversations.json, so run.py replaces the fact parser with a stub (FULL=1 keeps it). Rankings identical to full ingest on 2 questions checked. ~8 s/question -> ~70 min for 500.
- Full run started: results.jsonl / run.log
- Coordinator dropped RG_FUSE variant mid-run; run already ~77% done with both in one pass, so it finished and fuse is ignored in report.py.
- Coordinator dropped RG_FUSE mid-run (~77% done, fuse computed in same pass); run finished, fuse ignored in report.py.
- DONE: 500/500 in 5080 s (84.7 min). Tables in report.md (python report.py results.jsonl). Smoke: smoke.jsonl (full parser), fast.jsonl.
