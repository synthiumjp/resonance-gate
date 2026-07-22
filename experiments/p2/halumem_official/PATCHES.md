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
