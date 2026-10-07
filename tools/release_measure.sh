# Release re-measurement (2026-10-07): every headline number on ONE commit.
# Runs on the Mac (heavy work never on WSL). Usage, from WSL:
#   git archive --format=tar <commit> | ssh <mac> 'rm -rf ~/jpwork/sdr-release && mkdir -p ~/jpwork/sdr-release && tar -x -C ~/jpwork/sdr-release'
#   ssh <mac> 'cd ~/jpwork/sdr-release && echo <commit> > COMMIT && nohup bash tools/release_measure.sh > ~/jpwork/release.log 2>&1 &'
# Needs: the 14B reader/judge on :8090; the competitors' and baselines' raw
# returns from earlier runs (they do not change with our commit) are copied.
# Held-out sets report counts only.
set -u
W=$HOME/jpwork/sdr-release
P=$HOME/jpwork/sdr-venv/bin/python
export STANZA_RESOURCES_DIR=$HOME/jpwork/stanza_resources_114 HF_HUB_OFFLINE=1
NOTES=${NOTES_MODELS:-}          # e.g. "small:$HOME/jpwork/distil/ort_r6"
echo "== release measure $(cat $W/COMMIT 2>/dev/null) $(date)"

echo "== 1. full suite"
(cd $W && PYTHONPATH=$W/server $P -m pytest -q rgx experiments/p2 tools server 2>&1 | grep -E "^FAILED|passed|failed" | head -8)

echo "== 2. LoCoMo test (convs 2-9), default and each notes model"
cd $W/bench/locomo
export RG_REPO=$W LOCOMO_DATA=$HOME/jpwork/locomo10.json LOCOMO_TOP_K=5
export LOCOMO_LLM_BASE=http://127.0.0.1:8090/v1 LOCOMO_LLM_MODEL=qwen3-14b-a8cc1361.gguf
for spec in default: $NOTES; do
  name=${spec%%:*}; dir=${spec#*:}
  O=results/release_test_$name; rm -rf $O; mkdir -p $O
  for f in ctx_rag ans_rag ingest_rag ctx_mem0 ans_mem0 ingest_mem0; do cp $HOME/jpwork/sdr/bench/locomo/results/test/$f.jsonl $O/; done
  export LOCOMO_SCRATCH=$HOME/jpwork/locomo_stores_release_$name; rm -rf $LOCOMO_SCRATCH
  if [ -n "$dir" ]; then SOURCEDRECALL_NOTES_DIR=$dir $P retrieve.py sourcedrecall --convs 2-9 --out $O > $O/retrieve.log 2>&1
  else SOURCEDRECALL_NOTES=off $P retrieve.py sourcedrecall --convs 2-9 --out $O > $O/retrieve.log 2>&1; fi
  /usr/bin/python3 answer.py sourcedrecall --out $O > $O/answer.log 2>&1
  echo "-- locomo test $name"; /usr/bin/python3 score.py $O sourcedrecall mem0 rag | tee $O/score.md | grep -E "overall|multi-hop|temporal|single-hop|context tokens"
done

echo "== 3. LongMemEval-S retrieval (500 q)"
cd $W/bench/longmemeval
LME_DATA=$HOME/jpwork/lme/longmemeval_s_cleaned.json LME_SCRATCH=$HOME/jpwork/lme/scratch_release RG_REPO=$W \
  SOURCEDRECALL_NOTES=off $P run.py release_results.jsonl > release_run.log 2>&1
$P report.py release_results.jsonl | head -12

echo "== 4. false memory, held out (counts only)"
cd $W/bench/false_memory
export FM_JUDGE_OPENAI=http://127.0.0.1:8090/v1 FM_JUDGE_MODEL=qwen3-14b-a8cc1361.gguf
export OURS_PY=$P MEM0_PY=$HOME/jpwork/rg/.venv-judge/bin/python
num() { $P -c "
import json; r=json.load(open(\"$1/results.json\"))[\"systems\"]
for s in r:
  m=r[s][\"views_audited\"].get(\"answer\")
  if m: a=m[\"all\"]; print(\"$2\", s, {k:f\"{x[\"k\"]}/{x[\"n\"]}\" for k,x in a.items() if x})"; }
S=$HOME/jpwork/sdr/bench/false_memory
for set in v3 v4 codebg proj; do
  unset FM_DISTRACTORS FM_DISTRACTOR_COPIES
  case $set in
    v3) export FM_CASES=cases_v3.jsonl FM_OVERRIDES=audit_overrides_v3.json; H=$S/results_v3_ans_mfg0;;
    v4) export FM_CASES=cases_v4.jsonl FM_OVERRIDES=audit_overrides_v4.json; H=$S/results_v4_ans_mfg0;;
    codebg) export FM_CASES=cases_code_blind.jsonl FM_OVERRIDES=audit_overrides_code.json FM_DISTRACTORS=$PWD/distractors_code.jsonl FM_DISTRACTOR_COPIES=2; H=$S/results_codebg_blind;;
    proj) export FM_CASES=cases_projects_blind.jsonl FM_OVERRIDES=audit_overrides_projects.json; H=$S/results_proj2_blind;;
  esac
  R=$PWD/results_release_$set; rm -rf $R; mkdir -p $R
  cp $H/raw_rag.jsonl $H/answers_rag.jsonl $H/judge_log.jsonl $R/ 2>/dev/null
  [ -f $H/raw_mem0.jsonl ] && cp $H/raw_mem0.jsonl $H/answers_mem0.jsonl $R/
  export FM_RESULTS=$R FM_SCRATCH=$HOME/jpwork/fm_scratch_release_$set; rm -rf $FM_SCRATCH
  SOURCEDRECALL_NOTES=off bash run_all.sh ours > $R/run.log 2>&1
  /usr/bin/python3 answer.py sourcedrecall > $R/answer.log 2>&1; $P score.py > $R/score.log 2>&1
  num $R "$set release"
done
echo "== release measure done $(date)"
