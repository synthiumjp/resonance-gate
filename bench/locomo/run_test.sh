#!/bin/bash
# Test run: conversations 2-9, all questions of categories 1-4.
#   bash run_test.sh pre      # sourcedrecall + RAG retrieval (Linux CPU, no LLM)
#   bash run_test.sh llm      # Mem0 ingest + retrieval, then reader+judge for all three,
#                             # through the ssh tunnel to the llama_cpp server on the Mac
# Every step is resumable (jsonl caches in results/test).
S=${SCRATCH_DIR:-/tmp/claude-1000/-home-jp-rg/6594a3bb-1962-4d96-9cd9-065427ae8687/scratchpad}
export RG_REPO=${RG_REPO:-$S/rg_locomo} LOCOMO_SCRATCH=${LOCOMO_SCRATCH:-/tmp/locomo_stores}
OURS=~/rg_private/halumem/official/.venv/bin/python
M0=$S/fmbench/mem0venv/bin/python
cd "$(dirname "$0")"
A="--convs 2-9 --out results/test"
case $1 in
  pre)
    $OURS retrieve.py rag $A
    $OURS retrieve.py sourcedrecall $A ;;
  llm)
    export LOCOMO_LLM_BASE=http://127.0.0.1:18090/v1 LOCOMO_LLM_MODEL=${LOCOMO_LLM_MODEL:-qwen3-14b-a8cc1361.gguf}
    export LOCOMO_MEM0_LLM_BASE=$LOCOMO_LLM_BASE
    $M0 retrieve.py mem0 $A
    python3 answer.py rag sourcedrecall mem0 --out results/test
    python3 score.py results/test > results/test/score.md; cat results/test/score.md ;;
esac
