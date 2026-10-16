# The Claude column (2026-10-16): the release re-measurement's stored
# retrievals read by Claude (Batch API, JP's API credit), beside the local
# readers. Runs on the Mac after tools/release_measure2.sh, in the same tree:
#   bash bench/claude_runs.sh
# LoCoMo: Claude Sonnet 5.5 reads and judges sourcedrecall's, Mem0's and
# plain retrieval's contexts (the same prompts as answer.py). Pasted-text
# held-out sets: Claude Sonnet 5.5 reads every system's returns; the judge
# stays Qwen3-14B, as for the Phi-4 reader. Counts only for held-out sets.
# Expected cost: under $10 at Batch prices.
set -u
W=$(cd "$(dirname "$0")/.." && pwd)
P=$HOME/jpwork/sdr-venv/bin/python
V=$HOME/jpwork/claude-venv
[ -f "${CLAUDE_KEY_FILE:-$HOME/.anthropic_key}" ] || { echo "no API key file"; exit 1; }
[ -x $V/bin/python ] || { /opt/homebrew/bin/python3.12 -m venv $V && $V/bin/pip -q install anthropic; }
echo "== claude runs $(cat $W/COMMIT) $(date)"

echo "== LoCoMo test (convs 2-9), Claude reader and judge"
cd $W/bench/locomo
$V/bin/python answer_claude.py results/release_test_default results/claude_test_default \
  sourcedrecall mem0 rag > results/claude_test_default.log 2>&1 || { echo "locomo failed"; tail -5 results/claude_test_default.log; }
/usr/bin/python3 score.py results/claude_test_default sourcedrecall mem0 rag | tee results/claude_test_default/score.md \
  | grep -E "overall|multi-hop|temporal|single-hop|open"

echo "== pasted text, held out, Claude reader (judge Qwen3-14B)"
cd $W/bench/false_memory
export FM_JUDGE_OPENAI=http://127.0.0.1:8090/v1 FM_JUDGE_MODEL=qwen3-14b-a8cc1361.gguf
export FM_READER_SAME=1 FM_SAME_V7=1 FM_STRICT=1 FM_JUDGE_QUESTION=1
echo '{"overrides": []}' > $PWD/no_overrides_claude.json
for set in v11 v12 realpaste; do
  case $set in
    realpaste) export FM_CASES=cases_real_paste.jsonl; SYS="sourcedrecall rag";;
    *) export FM_CASES=cases_$set.jsonl; SYS="sourcedrecall rag agentmemory ai-memory";;
  esac
  R=$PWD/results_claude_$set; rm -rf $R; mkdir -p $R
  cp results_release2_${set}_qwen/raw_*.jsonl $R/
  FM_RESULTS=$R FM_READER_CLAUDE=claude-sonnet-5-5 $V/bin/python answer.py $SYS > $R/answer.log 2>&1 \
    || { echo "$set failed"; tail -3 $R/answer.log; continue; }
  FM_RESULTS=$R FM_OVERRIDES=$PWD/no_overrides_claude.json $P score.py > $R/score.log 2>&1
  echo "-- $set"; FM_RESULTS=$R $P v5_parts.py | tee $R/parts.txt
done
echo "== claude runs done $(date)"
