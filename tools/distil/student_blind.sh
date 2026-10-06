# student_blind.sh TAG : blind false memory v3, v4 with in-process notes from the student (counts only)
set -u
TAG=$1
export STANZA_RESOURCES_DIR=~/jpwork/stanza_resources_114
P=$HOME/jpwork/sdr-venv/bin/python
W=$HOME/jpwork/sdr-distil
cd $W/bench/false_memory
export FM_JUDGE_OPENAI=http://127.0.0.1:8090/v1 FM_JUDGE_MODEL=qwen3-14b-a8cc1361.gguf
export OURS_PY=$P MEM0_PY=$HOME/jpwork/rg/.venv-judge/bin/python
num() { $P -c "
import json; r=json.load(open(\"$1/results.json\"))[\"systems\"]
for s in r:
  m=r[s][\"views_audited\"].get(\"answer\")
  if m: a=m[\"all\"]; print(\"$2\", s, {k:f\"{x[\"k\"]}/{x[\"n\"]}\" for k,x in a.items() if x})"; }
for set in v3 v4; do
  export FM_CASES=cases_$set.jsonl FM_OVERRIDES=audit_overrides_$set.json
  H=$HOME/jpwork/sdr/bench/false_memory/results_${set}_ans_mfg0
  R=$PWD/results_${set}_ans_student_$TAG; rm -rf $R; mkdir -p $R
  cp $H/raw_rag.jsonl $H/answers_rag.jsonl $H/judge_log.jsonl $R/
  [ $set = v3 ] && cp $H/raw_mem0.jsonl $H/answers_mem0.jsonl $R/
  export FM_RESULTS=$R FM_SCRATCH=$HOME/jpwork/fm_scratch_student_${TAG}_$set
  SOURCEDRECALL_NOTES_DIR=$HOME/jpwork/distil/ort_$TAG bash run_all.sh ours > $R/run.log 2>&1
  /usr/bin/python3 answer.py sourcedrecall > $R/answer.log 2>&1; $P score.py > $R/score.log 2>&1
  num $R "$set student $TAG"
done
echo "== student blind $TAG done $(date)"
