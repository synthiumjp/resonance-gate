# end to end on sdr-dev15 (working tree: detection fixes + the cosine cut,
# RG_MSG_CUT=0.5) for all 9 dev sets; base is dev23's cut-off runs (same code
# with the cut off). Then Phi-4 (reader2.sh) on own, pasted, pasted2, stale2.
set -u
P=$HOME/jpwork/sdr-venv/bin/python
export STANZA_RESOURCES_DIR=$HOME/jpwork/stanza_resources_114 HF_HUB_OFFLINE=1 SOURCEDRECALL_NOTES=off OURS_PY=$P
export FM_JUDGE_OPENAI=http://127.0.0.1:8090/v1 FM_JUDGE_MODEL=qwen3-14b-a8cc1361.gguf
export FM_READER_SAME=1 FM_SAME_V7=1 FM_STRICT=1 FM_JUDGE_QUESTION=1 FM_OVERRIDES=/tmp/no_ov_dev20.json
cd $HOME/jpwork/sdr-dev15/bench/false_memory
D23=$HOME/jpwork/sdr-dev14/bench/false_memory
for set in own pasted pasted2 stale2 code projects decisions advice prefs; do
  export FM_CASES=cases_dev_$set.jsonl
  B=$PWD/results_dev25_${set}_cos50; rm -rf $B; mkdir -p $B
  cp $D23/results_dev23_${set}_cutoff/answers_sourcedrecall.jsonl $B/
  export FM_RESULTS=$B FM_SCRATCH=$HOME/jpwork/fm_scratch_dev25_$set RG_MSG_CUT=0.5; rm -rf $FM_SCRATCH
  bash run_all.sh ours > $B/run.log 2>&1
  unset RG_MSG_CUT
  /usr/bin/python3 answer.py sourcedrecall > $B/answer.log 2>&1
  $P score.py > $B/score.log 2>&1
  echo "== $set base (dev23 cut off)"; $P fair_summary.py $D23/results_dev23_${set}_cutoff | grep -v "^=="
  echo "== $set cos 0.5 (re-answered: $(grep -c answered $B/answer.log))"; $P fair_summary.py $B | grep -v "^=="
done
export FM_READER_OPENAI=http://127.0.0.1:8091/v1 FM_READER_MODEL=phi-4
for set in own pasted pasted2 stale2; do
  export FM_CASES=cases_dev_$set.jsonl
  R=$PWD/results_r2_${set}_cos50; rm -rf $R; mkdir -p $R
  cp $PWD/results_dev25_${set}_cos50/raw_sourcedrecall.jsonl $R/
  export FM_RESULTS=$R
  /usr/bin/python3 answer.py sourcedrecall > $R/answer.log 2>&1
  $P score.py > $R/score.log 2>&1
  echo "== $set cos 0.5, phi-4 (base: reader2.log cut off)"; $P fair_summary.py $R | grep -v "^=="
done
echo "dev25 done"
