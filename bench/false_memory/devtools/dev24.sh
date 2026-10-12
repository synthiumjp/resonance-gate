# relevance cut by bge-small cosine on fixed retrieval (recut.py cos:T, DENSE from densecheck.py) over dev20's base runs, all 9 dev sets
set -u
P=$HOME/jpwork/sdr-venv/bin/python
export STANZA_RESOURCES_DIR=$HOME/jpwork/stanza_resources_114 HF_HUB_OFFLINE=1 SOURCEDRECALL_NOTES=off
export FM_JUDGE_OPENAI=http://127.0.0.1:8090/v1 FM_JUDGE_MODEL=qwen3-14b-a8cc1361.gguf
export FM_READER_SAME=1 FM_SAME_V7=1 FM_STRICT=1 FM_JUDGE_QUESTION=1 FM_OVERRIDES=/tmp/no_ov_dev20.json
cd $HOME/jpwork/sdr-dev13/bench/false_memory
for set in own pasted pasted2 stale2 code projects decisions advice prefs; do
  export FM_CASES=cases_dev_$set.jsonl
  B=$PWD/results_dev20_$set
  echo "== $set base"; $P fair_summary.py $B | grep -v "^=="
  for v in cos:.50 cos:.48; do
    R=$PWD/results_dev24_${set}_$(echo $v | tr ':' '_'); rm -rf $R
    DENSE=$HOME/jpwork/dense/$set.jsonl $P $HOME/jpwork/recut.py $B $R $v
    export FM_RESULTS=$R
    /usr/bin/python3 answer.py sourcedrecall > $R/answer.log 2>&1
    $P score.py > $R/score.log 2>&1
    echo "== $set $v"; $P fair_summary.py $R | grep -v "^=="
  done
done
echo "dev24 done"
