#!/bin/bash
# The Claude column (2026-10-16): the release re-measurement's stored
# retrievals read by Claude (Batch API), beside the local readers. Runs on
# the machine that holds the API key (~/.anthropic_key, and
# ~/.anthropic_workspace for a key not scoped to a workspace): it fetches the
# inputs from the benchmark machine ($SDR_MAC, the release tree), sends the
# batches from here, and puts the answers back there, where scoring runs as
# for every other run.
#   bash bench/claude_runs.sh <release commit>
# LoCoMo: Claude Sonnet 5.5 reads and judges sourcedrecall's, Mem0's and
# plain retrieval's contexts (answer.py's prompts). Pasted-text held-out
# sets: Claude Sonnet 5.5 reads every system's returns; the judge stays
# Qwen3-14B, as for the Phi-4 reader. Counts only for held-out sets.
# Expected cost: under $10 at Batch prices.
set -u
C=$1
HERE=$(cd "$(dirname "$0")" && pwd)
. "$HERE/../.hosts.env"
RT=jpwork/sdr-release-$C                 # the release tree on the Mac
L=$HOME/claude_runs/$C; mkdir -p $L      # local working copies
PY=$HOME/claude-venv/bin/python
echo "== claude runs $C $(date)"

echo "== LoCoMo test (convs 2-9), Claude reader and judge"
mkdir -p $L/locomo_src
for s in sourcedrecall mem0 rag; do
  scp -q $SDR_MAC:$RT/bench/locomo/results/release_test_default/ctx_$s.jsonl $L/locomo_src/
done
$PY $HERE/locomo/answer_claude.py $L/locomo_src $L/claude_test_default sourcedrecall mem0 rag \
  || { echo "locomo failed"; exit 1; }
ssh -o BatchMode=yes $SDR_MAC "mkdir -p $RT/bench/locomo/results/claude_test_default"
scp -q $L/claude_test_default/* $SDR_MAC:$RT/bench/locomo/results/claude_test_default/
ssh -o BatchMode=yes $SDR_MAC "cd $RT/bench/locomo && /usr/bin/python3 score.py results/claude_test_default sourcedrecall mem0 rag | tee results/claude_test_default/score.md | grep -E 'overall|multi-hop|temporal|single-hop|open'"

echo "== pasted text, held out, Claude reader (judge Qwen3-14B on the Mac)"
for set in v11 v12 realpaste; do
  case $set in
    realpaste) cases=cases_real_paste.jsonl; SYS="sourcedrecall rag";;
    *) cases=cases_$set.jsonl; SYS="sourcedrecall rag agentmemory ai-memory";;
  esac
  R=$L/results_claude_$set; mkdir -p $R
  for s in $SYS; do
    scp -q $SDR_MAC:$RT/bench/false_memory/results_release2_${set}_qwen/raw_$s.jsonl $R/
  done
  scp -q $SDR_MAC:$RT/bench/false_memory/$cases $L/
  FM_RESULTS=$R FM_CASES=$L/$cases FM_READER_SAME=1 FM_SAME_V7=1 FM_READER_CLAUDE=claude-sonnet-5-5 \
    $PY $HERE/false_memory/answer.py $SYS || { echo "$set failed"; continue; }
  ssh -o BatchMode=yes $SDR_MAC "mkdir -p $RT/bench/false_memory/results_claude_$set"
  scp -q $R/* $SDR_MAC:$RT/bench/false_memory/results_claude_$set/
  ssh -o BatchMode=yes $SDR_MAC "cd $RT/bench/false_memory && echo '{\"overrides\": []}' > no_overrides_claude.json && \
    export FM_JUDGE_OPENAI=http://127.0.0.1:8090/v1 FM_JUDGE_MODEL=qwen3-14b-a8cc1361.gguf FM_STRICT=1 FM_JUDGE_QUESTION=1 FM_CASES=$cases && \
    FM_RESULTS=\$PWD/results_claude_$set FM_OVERRIDES=\$PWD/no_overrides_claude.json ~/jpwork/sdr-venv/bin/python score.py > results_claude_$set/score.log 2>&1; \
    echo '-- $set'; FM_RESULTS=\$PWD/results_claude_$set ~/jpwork/sdr-venv/bin/python v5_parts.py | tee results_claude_$set/parts.txt"
done
echo "== claude runs done $(date)"
