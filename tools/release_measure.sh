# Release re-measurement (2026-10-07): every headline number on ONE commit.
# Runs on the Mac (heavy work never on WSL). Usage, from WSL:
#   git archive --format=tar <commit> | ssh <mac> 'rm -rf ~/jpwork/sdr-release && mkdir -p ~/jpwork/sdr-release && tar -x -C ~/jpwork/sdr-release'
#   ssh <mac> 'cd ~/jpwork/sdr-release && echo <commit> > COMMIT && nohup bash tools/release_measure.sh > ~/jpwork/release.log 2>&1 &'
# (W below can be overridden: W=~/jpwork/sdr-release-<commit> bash tools/release_measure.sh)
# Needs: the 14B reader/judge on :8090; the competitors' and baselines' raw
# returns from earlier runs (they do not change with our commit) are copied.
# Held-out sets report counts only.
set -u
W=${W:-$HOME/jpwork/sdr-release}
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

echo "== 4. false memory, held out (counts only), the fair protocol (v7)"
# 2026-10-12 (review 1.2): this step used the old protocol (no reader-same,
# no strict scoring, the judge without the question) and copied plain
# retrieval's old answers, so its counts did not compare with the README
# table. Now as fair_run.sh / v10_run.sh: every system's saved returns go to
# the same reader with v7's instruction, the judge sees the question, strict
# scoring; the blinded audit of the fair rerun is applied where an answer is
# the one it audited (an answer it never saw keeps the judge's verdict).
cd $W/bench/false_memory
export FM_JUDGE_OPENAI=http://127.0.0.1:8090/v1 FM_JUDGE_MODEL=qwen3-14b-a8cc1361.gguf
export FM_READER_SAME=1 FM_SAME_V7=1 FM_STRICT=1 FM_JUDGE_QUESTION=1
export OURS_PY=$P MEM0_PY=$HOME/jpwork/rg/.venv-judge/bin/python
num() { $P -c "
import json; r=json.load(open(\"$1/results.json\"))[\"systems\"]
for s in r:
  m=r[s][\"views_audited\"].get(\"answer\")
  if m: a=m[\"all\"]; print(\"$2\", s, {k:f\"{x[\"k\"]}/{x[\"n\"]}\" for k,x in a.items() if x})"; }
S=$HOME/jpwork/sdr/bench/false_memory; H=$HOME/jpwork/h2h
for set in v3 v4 codebg proj; do
  unset FM_DISTRACTORS FM_DISTRACTOR_COPIES
  case $set in
    v3) export FM_CASES=cases_v3.jsonl; SRC=$S/results_v3_ans_mfg0; OTHERS="rag mem0";;
    v4) export FM_CASES=cases_v4.jsonl; SRC=$H/results_h2h_v4; OTHERS="rag agentmemory ai-memory";;
    codebg) export FM_CASES=cases_code_blind.jsonl FM_DISTRACTORS=$PWD/distractors_code.jsonl FM_DISTRACTOR_COPIES=2
            SRC=$H/results_h2h_codebg; OTHERS="rag agentmemory ai-memory";;
    proj) export FM_CASES=cases_projects_blind.jsonl; SRC=$H/results_h2h_proj; OTHERS="rag agentmemory ai-memory";;
  esac
  export FM_OVERRIDES=$PWD/audit_overrides_results_fair_${set}_A.json
  R=$PWD/results_release_$set; rm -rf $R; mkdir -p $R
  for o in $OTHERS; do cp $SRC/raw_$o.jsonl $R/; done
  export FM_RESULTS=$R FM_SCRATCH=$HOME/jpwork/fm_scratch_release_$set; rm -rf $FM_SCRATCH
  SOURCEDRECALL_NOTES=off bash run_all.sh ours > $R/run.log 2>&1
  /usr/bin/python3 answer.py sourcedrecall $OTHERS > $R/answer.log 2>&1; $P score.py > $R/score.log 2>&1
  num $R "$set release"
done
echo "== release measure done $(date)"
