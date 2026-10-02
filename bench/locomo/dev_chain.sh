#!/bin/bash
# Dev validation (conversations 0-1, first 3 sessions, 15 questions each). Retrieval on this
# box; reader, judge and Mem0's LLM through the tunnel to the llama_cpp server on the Mac.
S=/tmp/claude-1000/-home-jp-rg/6594a3bb-1962-4d96-9cd9-065427ae8687/scratchpad
export RG_REPO=$S/rg_locomo LOCOMO_SCRATCH=/tmp/locomo_stores
export LOCOMO_LLM_BASE=http://127.0.0.1:18090/v1 LOCOMO_LLM_MODEL=qwen3-14b-a8cc1361.gguf LOCOMO_MEM0_LLM_BASE=http://127.0.0.1:18090/v1
OURS=~/rg_private/halumem/official/.venv/bin/python
M0=$S/fmbench/mem0venv/bin/python
cd /home/jp/rg/bench/locomo
A="--convs 0-1 --out results/dev --max-sessions 3 --sample 15"
$OURS retrieve.py rag $A
$OURS retrieve.py sourcedrecall $A
$M0 retrieve.py mem0 $A
python3 answer.py rag sourcedrecall mem0 --out results/dev
python3 score.py results/dev | tee results/dev/score.md
echo DEV_DONE
