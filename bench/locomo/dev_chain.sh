#!/bin/bash
# Dev validation on this box (conversations 0-1, first 3 sessions, 15 questions each, Ollama CPU).
S=/tmp/claude-1000/-home-jp-rg/6594a3bb-1962-4d96-9cd9-065427ae8687/scratchpad
export RG_REPO=$S/rg_locomo LOCOMO_SCRATCH=/tmp/locomo_stores LOCOMO_LLM_MODEL=qwen3-14b-fm
OURS=~/rg_private/halumem/official/.venv/bin/python
M0=$S/fmbench/mem0venv/bin/python
cd /home/jp/rg/bench/locomo
A="--convs 0-1 --out results/dev --max-sessions 3 --sample 15"
$OURS retrieve.py rag $A
$OURS retrieve.py sourcedrecall $A
python3 answer.py rag sourcedrecall --out results/dev
$M0 retrieve.py mem0 $A
python3 answer.py mem0 --out results/dev
python3 score.py results/dev
echo DEV_DONE
