# a second reader of another family (Phi-4 14B, microsoft/phi-4-gguf
# phi-4-Q4_K.gguf, sha256 5652b9be0ea4ae2842130d04fe31bc869fcb99a2b7106c53b4e754a343fd688f,
# llama_cpp.server on 127.0.0.1:8091 with the GGUF's own chat template) over
# dev23's blocks, cut off and at -9; the judge stays Qwen3-14B. Plain
# retrieval's own-set lines (dev15) re-answered by the same reader.
set -u
P=$HOME/jpwork/sdr-venv/bin/python
export FM_JUDGE_OPENAI=http://127.0.0.1:8090/v1 FM_JUDGE_MODEL=qwen3-14b-a8cc1361.gguf
export FM_READER_OPENAI=http://127.0.0.1:8091/v1 FM_READER_MODEL=phi-4
export FM_READER_SAME=1 FM_SAME_V7=1 FM_STRICT=1 FM_JUDGE_QUESTION=1 FM_OVERRIDES=/tmp/no_ov_dev20.json
cd $HOME/jpwork/sdr-dev14/bench/false_memory
R=$PWD/results_r2_own_rag; rm -rf $R; mkdir -p $R
cp $HOME/jpwork/sdr-dev11/bench/false_memory/results_dev15_own/raw_rag.jsonl $R/
export FM_CASES=cases_dev_own.jsonl FM_RESULTS=$R
/usr/bin/python3 answer.py rag > $R/answer.log 2>&1
$P score.py > $R/score.log 2>&1
echo "== own rag, phi-4"; $P fair_summary.py $R | grep -v "^=="
for set in own pasted pasted2 stale2; do
  export FM_CASES=cases_dev_$set.jsonl
  while [ ! -s $PWD/results_dev23_${set}_cut-9/score.log ]; do sleep 30; done
  for v in off -9; do
    R=$PWD/results_r2_${set}_cut$v; rm -rf $R; mkdir -p $R
    cp $PWD/results_dev23_${set}_cut$v/raw_sourcedrecall.jsonl $R/
    export FM_RESULTS=$R
    /usr/bin/python3 answer.py sourcedrecall > $R/answer.log 2>&1
    $P score.py > $R/score.log 2>&1
    echo "== $set cut $v, phi-4"; $P fair_summary.py $R | grep -v "^=="
  done
done
echo "reader2 done"
