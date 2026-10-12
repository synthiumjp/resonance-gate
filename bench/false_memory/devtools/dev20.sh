# end-to-end base runs on sdr-dev13 (= e9ef773's block code + a score log,
# RG_MSG_LOG) for all 9 dev sets: per shown message its search score, rank and
# route, for relevance-cutoff experiments on fixed retrieval. Base answers are
# copied in, so answer.py only calls the reader where a block changed.
set -u
P=$HOME/jpwork/sdr-venv/bin/python
export STANZA_RESOURCES_DIR=$HOME/jpwork/stanza_resources_114 HF_HUB_OFFLINE=1 SOURCEDRECALL_NOTES=off OURS_PY=$P
export FM_JUDGE_OPENAI=http://127.0.0.1:8090/v1 FM_JUDGE_MODEL=qwen3-14b-a8cc1361.gguf
export FM_READER_SAME=1 FM_SAME_V7=1 FM_STRICT=1 FM_JUDGE_QUESTION=1
echo '{"overrides": []}' > /tmp/no_ov_dev20.json; export FM_OVERRIDES=/tmp/no_ov_dev20.json
cd $HOME/jpwork/sdr-dev13/bench/false_memory
for set in own pasted pasted2 stale2 code projects decisions advice prefs; do
  case $set in own|pasted|pasted2|stale2) O=$HOME/jpwork/sdr-dev12/bench/false_memory/results_dev17_$set;;
               *) O=$HOME/jpwork/sdr-dev11/bench/false_memory/results_dev16_$set;; esac
  export FM_CASES=cases_dev_$set.jsonl
  B=$PWD/results_dev20_$set; rm -rf $B; mkdir -p $B
  cp $O/answers_sourcedrecall.jsonl $B/
  export FM_RESULTS=$B FM_SCRATCH=$HOME/jpwork/fm_scratch_dev20_$set RG_MSG_LOG=$B/msglog.jsonl; rm -rf $FM_SCRATCH
  bash run_all.sh ours > $B/run.log 2>&1
  unset RG_MSG_LOG
  /usr/bin/python3 answer.py sourcedrecall > $B/answer.log 2>&1
  $P score.py > $B/score.log 2>&1
  echo "== $set base (dev17/16)"; FM_RESULTS=$O $P fair_summary.py $O | grep -v "^==" | grep -v rag
  echo "== $set dev20 (re-answered: $(grep -c answered $B/answer.log))"; $P fair_summary.py $B | grep -v "^=="
done
echo "dev20 done"
