# Phi-4 (see reader2.sh) over dev24's cosine-cut blocks and their dev20 base
set -u
P=$HOME/jpwork/sdr-venv/bin/python
export FM_JUDGE_OPENAI=http://127.0.0.1:8090/v1 FM_JUDGE_MODEL=qwen3-14b-a8cc1361.gguf
export FM_READER_OPENAI=http://127.0.0.1:8091/v1 FM_READER_MODEL=phi-4
export FM_READER_SAME=1 FM_SAME_V7=1 FM_STRICT=1 FM_JUDGE_QUESTION=1 FM_OVERRIDES=/tmp/no_ov_dev20.json
cd $HOME/jpwork/sdr-dev13/bench/false_memory
for set in own pasted pasted2 stale2; do
  export FM_CASES=cases_dev_$set.jsonl
  for v in cos_.50 cos_.48; do
    while [ ! -s $PWD/results_dev24_${set}_$v/score.log ]; do sleep 30; done
    R=$PWD/results_r2b_${set}_$v; rm -rf $R; mkdir -p $R
    cp $PWD/results_dev24_${set}_$v/raw_sourcedrecall.jsonl $R/
    export FM_RESULTS=$R
    /usr/bin/python3 answer.py sourcedrecall > $R/answer.log 2>&1
    $P score.py > $R/score.log 2>&1
    echo "== $set $v, phi-4"; $P fair_summary.py $R | grep -v "^=="
  done
done
echo "reader2b done"
