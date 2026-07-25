# Official HaluMem harness — exact deviations (entry 89)

Harness: github.com/MemTensor/HaluMem @ clone of 2026-07-23, run UNMODIFIED
except for the following, each forced by the no-paid-API rule or by adding
our frame; metric definitions, judge prompts, and aggregation are theirs.

1. eval/eval_rgp2.py (ADDED, copy in this dir): our frame adapter, following
   eval_memzero.py's structure. Ingestion = pure extraction-cache replay
   (zero LLM calls); answers = halumem_run.answer_question (non-generative).
2. eval/.env: OPENAI_BASE_URL=http://localhost:8090/v1 (LOCAL llama-cpp
   server, GPU), OPENAI_MODEL=qwen3:14b, RG_PREFIX_NO_THINK=1.
   => the judge MODEL is local qwen3:14b, not the paper's OpenAI judge.
   This is the one caveat on cross-row comparability with published numbers.
3. eval/llms.py: (a) RG_NO_THINK=1 path routing via ollama native /api/chat
   (written for the CPU-ollama attempt, off by default); (b)
   RG_PREFIX_NO_THINK=1 path prepending qwen3's "/no_think" soft switch and
   stripping empty <think> blocks from responses. No prompt/logic changes.
4. eval/evaluation.py line 513: added "rgp2" to the argparse frame choices
   list. No other change.

Runtime: llama-cpp OpenAI server on the 7900 GRE (all layers ROCm-offloaded),
~23,653 judge calls. ollama itself ran CPU-only in this session (its ROCm
detection fails under WSL2 where llama-cpp's works), measured ~90s/call =
~25 days serial -- hence the server route.

5. eval/evaluation.py: exposed their existing main(user_num=20) parameter as
   a --user_num CLI flag (pure pass-through). The official run uses
   --user_num 10 (first 10 users): the full-benchmark 0/3,189 two-judge
   result already exists for discovery; the official harness run is for
   method comparability, where 10 users (~1,700 officially-judged QA items)
   retains ample power. Per-user variance measured from the 20-user fleet
   (correct-count stdev/mean ~16%) supports subsetting; extension to 20 is
   free later via their per-user tmp2/ checkpoints.

6. eval/evaluation.py: max_workers default 10 -> 4 (infra only, no metric
   effect: all judge calls serialize on the single local GPU inference slot;
   10 forked workers were pure RAM pressure on a 15GB host that OOM-crashed
   mid-run on 2026-07-23).

7. eval/eval_rgp2.py: extraction-cache suffix now env-selected (_v5 when
   RG_EXTRACT_V5 else _v4) -- round 3 uses the v5.1 narrative extractor.
