# Held-out v5, one run (docs/PREREG_HELDOUT_V5.md). On the Mac, from the
# frozen tree. Counts only: nothing here prints scenario text.
set -u
cd "$(dirname "$0")"
P=${OURS_PY:-$HOME/jpwork/sdr-venv/bin/python}
export STANZA_RESOURCES_DIR=${STANZA_RESOURCES_DIR:-$HOME/jpwork/stanza_resources_114}
export HF_HUB_OFFLINE=1 SOURCEDRECALL_NOTES=off
export FM_CASES=cases_v5.jsonl FM_RESULTS=$PWD/results_v5 FM_OVERRIDES=$PWD/audit_overrides_v5.json
export FM_JUDGE_OPENAI=http://127.0.0.1:8090/v1 FM_JUDGE_MODEL=qwen3-14b-a8cc1361.gguf
export OURS_PY=$P MEM0_PY=${MEM0_PY:-$HOME/jpwork/rg/.venv-judge/bin/python}
export FM_SCRATCH=$HOME/jpwork/fm_scratch_v5
[ -f $FM_OVERRIDES ] || echo '{"_note": "no audit yet", "overrides": []}' > $FM_OVERRIDES
mkdir -p $FM_RESULTS
step=${1:-all}
if [ $step = all ] || [ $step = run ]; then
  echo "== v5 run $(cat ../../COMMIT 2>/dev/null) $(date)"
  rm -rf $FM_SCRATCH
  bash run_all.sh rag ours > $FM_RESULTS/run.log 2>&1
  /usr/bin/python3 answer.py sourcedrecall rag > $FM_RESULTS/answer.log 2>&1
fi
echo "== score $(date)"
$P score.py > $FM_RESULTS/score.log 2>&1
$P v5_parts.py | tee $FM_RESULTS/parts.txt
echo "== labels (H2, H3, H7)"
for part in B C; do
  $P -c "
import json
with open('$FM_RESULTS/cases_v5_$part.jsonl','w') as f:
    for l in open('cases_v5.jsonl'):
        if json.loads(l)['subtype'].startswith('${part}_'): f.write(l)"
  echo "-- part $part"; $P screen_labels.py $FM_RESULTS $FM_RESULTS/cases_v5_$part.jsonl --counts-only 2>&1 | grep -v Warn
done
echo "-- whole set"; $P screen_labels.py $FM_RESULTS cases_v5.jsonl --counts-only 2>&1 | grep -v Warn | tee $FM_RESULTS/labels.txt
if [ $step = all ] || [ $step = run ]; then
  echo "== claim check (H5), part E"
  mkdir -p $FM_RESULTS/E
  $P -c "
import json
with open('$FM_RESULTS/E/cases_v5.jsonl','w') as f:
    for l in open('cases_v5.jsonl'):
        if json.loads(l)['subtype'].startswith('E_'): f.write(l)"
  FM_CASES=$FM_RESULTS/E/cases_v5.jsonl CHECK_OUT=$FM_RESULTS/check.jsonl $P check_eval.py --positives positives_v5.jsonl --counts-only 2>&1 | grep -v Warn | tee $FM_RESULTS/check.txt
  echo "== advice (H6)"
  $P v5_advice.py 2>&1 | grep -v Warn | tee $FM_RESULTS/advice.txt
fi
echo "== v5 done $(date)"
