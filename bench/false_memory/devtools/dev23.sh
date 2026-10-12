# end to end on sdr-dev14 (working tree after 124d29b: detection fixes + the
# relevance cut in memory_api, RG_MSG_CUT): all 9 dev sets with the cut off
# and at -9. Answers from dev20 are copied in, so only changed blocks are
# re-answered.
set -u
P=$HOME/jpwork/sdr-venv/bin/python
export STANZA_RESOURCES_DIR=$HOME/jpwork/stanza_resources_114 HF_HUB_OFFLINE=1 SOURCEDRECALL_NOTES=off OURS_PY=$P
export FM_JUDGE_OPENAI=http://127.0.0.1:8090/v1 FM_JUDGE_MODEL=qwen3-14b-a8cc1361.gguf
export FM_READER_SAME=1 FM_SAME_V7=1 FM_STRICT=1 FM_JUDGE_QUESTION=1 FM_OVERRIDES=/tmp/no_ov_dev20.json
cd $HOME/jpwork/sdr-dev14/bench/false_memory
for set in own pasted pasted2 stale2 code projects decisions advice prefs; do
  export FM_CASES=cases_dev_$set.jsonl
  for v in off -9; do
    B=$PWD/results_dev23_${set}_cut$v; rm -rf $B; mkdir -p $B
    cp $HOME/jpwork/sdr-dev13/bench/false_memory/results_dev20_$set/answers_sourcedrecall.jsonl $B/
    export FM_RESULTS=$B FM_SCRATCH=$HOME/jpwork/fm_scratch_dev23_$set RG_MSG_CUT=$v; rm -rf $FM_SCRATCH
    bash run_all.sh ours > $B/run.log 2>&1
    unset RG_MSG_CUT
    /usr/bin/python3 answer.py sourcedrecall > $B/answer.log 2>&1
    $P score.py > $B/score.log 2>&1
    echo "== $set cut $v (re-answered: $(grep -c answered $B/answer.log))"; $P fair_summary.py $B | grep -v "^=="
  done
done
echo "dev23 done"
