#!/usr/bin/env bash
# Full rerun. Usage: bash run_all.sh [step ...]   (steps: cases rag ours mem0 validate score)
# No argument = all steps in order. Steps are resumable (raw_*.jsonl is appended
# per scenario and finished scenarios are skipped); delete results/raw_*.jsonl
# for a clean run.
#
# Environments (override with env vars):
#   OURS_PY   python with stanza + the sourcedrecall dependencies
#   MEM0_PY   venv with mem0ai ollama sentence-transformers  (also runs the RAG baseline)
#   FM_SCRATCH  scratch dir for per-scenario stores
set -euo pipefail
cd "$(dirname "$0")"
OURS_PY=${OURS_PY:-$HOME/rg_private/halumem/official/.venv/bin/python}
MEM0_PY=${MEM0_PY:-python3}
export FM_SCRATCH=${FM_SCRATCH:-/tmp/fm_scratch}
mkdir -p "$FM_SCRATCH" results
export MEM0_TELEMETRY=False   # HF is offline for rag/ours (set per step); Mem0 may fetch fastembed's BM25 model once
CAP=(systemd-run --user --scope -p MemoryMax=6G -p MemorySwapMax=0)   # memory cap for heavy steps
steps=("$@"); [ ${#steps[@]} -eq 0 ] && steps=(cases rag ours mem0 validate score)
for s in "${steps[@]}"; do
  echo "=== $s $(date +%T)"
  case $s in
    cases)    python3 build_cases.py ;;
    rag)      HF_HUB_OFFLINE=1 "${CAP[@]}" "$MEM0_PY" -u run_system.py rag ;;
    ours)     HF_HUB_OFFLINE=1 "${CAP[@]}" "$OURS_PY" -u run_system.py sourcedrecall ;;
    mem0)     ollama create qwen3-14b-fm -f Modelfile.mem0
              ollama pull nomic-embed-text
              "${CAP[@]}" "$MEM0_PY" -u run_system.py mem0 ;;
    validate) python3 judge_validate.py ;;
    score)    python3 score.py ;;
  esac
done
