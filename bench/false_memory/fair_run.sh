# The fair rerun (adversarial review 2026-10-09, A1-A5), on the Mac, from a
# tree of one commit. Every system's saved returns go to the same reader with
# the same instruction (A: sourcedrecall keeps its own rules; B: without them);
# the judge sees the question; strict scoring. No audit overrides here: the
# blinded audit is applied afterwards. Counts only.
set -u
cd "$(dirname "$0")"
P=${OURS_PY:-$HOME/jpwork/sdr-venv/bin/python}
export STANZA_RESOURCES_DIR=${STANZA_RESOURCES_DIR:-$HOME/jpwork/stanza_resources_114}
export HF_HUB_OFFLINE=1 SOURCEDRECALL_NOTES=off OURS_PY=$P MEM0_PY=$HOME/jpwork/rg/.venv-judge/bin/python
export FM_JUDGE_OPENAI=http://127.0.0.1:8090/v1 FM_JUDGE_MODEL=qwen3-14b-a8cc1361.gguf
export FM_READER_SAME=1 FM_STRICT=1 FM_JUDGE_QUESTION=1
curl -s -m 10 http://127.0.0.1:8090/v1/models >/dev/null || { echo "reader server on 8090 is down"; exit 1; }
echo '{"_note": "no audit yet", "overrides": []}' > $PWD/no_overrides.json
export FM_OVERRIDES=$PWD/no_overrides.json
H=$HOME/jpwork/h2h; S=$HOME/jpwork/sdr/bench/false_memory
echo "== fair run $(cat ../../COMMIT 2>/dev/null) $(date)"
for set in v3 v4 codebg proj; do
  unset FM_DISTRACTORS FM_DISTRACTOR_COPIES
  case $set in
    v3) export FM_CASES=cases_v3.jsonl; SRC=$S/results_v3_ans_mfg0; OTHERS="rag mem0";;
    v4) export FM_CASES=cases_v4.jsonl; SRC=$H/results_h2h_v4; OTHERS="rag agentmemory ai-memory";;
    codebg) export FM_CASES=cases_code_blind.jsonl FM_DISTRACTORS=$PWD/distractors_code.jsonl FM_DISTRACTOR_COPIES=2
            SRC=$H/results_h2h_codebg; OTHERS="rag agentmemory ai-memory";;
    proj) export FM_CASES=cases_projects_blind.jsonl; SRC=$H/results_h2h_proj; OTHERS="rag agentmemory ai-memory";;
  esac
  A=$PWD/results_fair_${set}_A; B=$PWD/results_fair_${set}_B
  rm -rf $A $B; mkdir -p $A $B
  for o in $OTHERS; do cp $SRC/raw_$o.jsonl $A/; done
  export FM_RESULTS=$A FM_SCRATCH=$HOME/jpwork/fm_scratch_fair_$set; rm -rf $FM_SCRATCH
  bash run_all.sh ours > $A/run.log 2>&1
  /usr/bin/python3 answer.py sourcedrecall $OTHERS > $A/answer.log 2>&1
  $P score.py > $A/score.log 2>&1
  cp $A/raw_*.jsonl $B/; for o in $OTHERS; do cp $A/answers_$o.jsonl $B/; done
  FM_RESULTS=$B FM_OURS_RULES=0 /usr/bin/python3 answer.py sourcedrecall > $B/answer.log 2>&1
  FM_RESULTS=$B $P score.py > $B/score.log 2>&1
  echo "-- $set"; $P fair_summary.py $A $B
done
echo "== fair run done $(date)"
