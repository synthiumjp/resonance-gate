set -u
P=$HOME/jpwork/sdr-venv/bin/python
export STANZA_RESOURCES_DIR=$HOME/jpwork/stanza_resources_114 HF_HUB_OFFLINE=1 SOURCEDRECALL_NOTES=off OURS_PY=$P
export FM_JUDGE_OPENAI=http://127.0.0.1:8090/v1 FM_JUDGE_MODEL=qwen3-14b-a8cc1361.gguf
export FM_READER_SAME=1 FM_SAME_V7=1 FM_STRICT=1 FM_JUDGE_QUESTION=1 FM_OVERRIDES=/tmp/no_ov_dev17.json
for set in own pasted pasted2 stale2 code projects decisions advice prefs; do
  case $set in own|pasted|pasted2|stale2) T=sdr-dev12; B=results_dev17_$set;; *) T=sdr-dev11; B=results_dev16_$set;; esac
  cd $HOME/jpwork/$T/bench/false_memory
  export FM_CASES=cases_dev_$set.jsonl
  B=$PWD/$B; R=$PWD/results_dev19_${set}_first; rm -rf $R
  $P $HOME/jpwork/reblock2.py $B $R
  export FM_RESULTS=$R
  /usr/bin/python3 answer.py sourcedrecall > $R/answer.log 2>&1
  $P score.py > $R/score.log 2>&1
  echo "== $set base"; FM_RESULTS=$B $P fair_summary.py $B | grep -v "^==" | grep -v "rag"
  echo "== $set first"; $P fair_summary.py $R | grep -v "^=="
done
echo "dev19 done"
