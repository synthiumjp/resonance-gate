# rules rewrites on fixed retrieval: base runs (sourcedrecall) per set, then each variant re-answered and judged
set -u
P=$HOME/jpwork/sdr-venv/bin/python
export STANZA_RESOURCES_DIR=$HOME/jpwork/stanza_resources_114 HF_HUB_OFFLINE=1 SOURCEDRECALL_NOTES=off OURS_PY=$P
export FM_JUDGE_OPENAI=http://127.0.0.1:8090/v1 FM_JUDGE_MODEL=qwen3-14b-a8cc1361.gguf
export FM_READER_SAME=1 FM_SAME_V7=1 FM_STRICT=1 FM_JUDGE_QUESTION=1
echo '{"overrides": []}' > /tmp/no_ov_dev17.json; export FM_OVERRIDES=/tmp/no_ov_dev17.json
cd $HOME/jpwork/sdr-dev12/bench/false_memory
for set in own pasted pasted2 stale2; do
  export FM_CASES=cases_dev_$set.jsonl
  B=$PWD/results_dev17_$set
  if [ ! -s $B/raw_sourcedrecall.jsonl ]; then
    rm -rf $B; mkdir -p $B
    export FM_RESULTS=$B FM_SCRATCH=$HOME/jpwork/fm_scratch_dev17_$set; rm -rf $FM_SCRATCH
    bash run_all.sh ours > $B/run.log 2>&1
    /usr/bin/python3 answer.py sourcedrecall > $B/answer.log 2>&1
    $P score.py > $B/score.log 2>&1
  fi
  echo "== $set base"; $P fair_summary.py $B | grep -v "^=="
  for v in compact_own; do
    R=${B}_$v; rm -rf $R
    $P $HOME/jpwork/reblock.py $B $R $v
    export FM_RESULTS=$R
    /usr/bin/python3 answer.py sourcedrecall > $R/answer.log 2>&1
    $P score.py > $R/score.log 2>&1
    echo "== $set $v"; $P fair_summary.py $R | grep -v "^=="
  done
  export FM_RESULTS=$B
done
echo "dev17 done"
