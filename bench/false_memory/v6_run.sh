# Held-out v6, one run (docs/PREREG_HELDOUT_V6.md), on the Mac from a tree of
# the frozen commit. The fair protocol: every system's returns to the same
# reader with the same instruction, the judge given the question, strict
# scoring; the blinded audit follows (blind_audit.py). Counts only.
set -u
cd "$(dirname "$0")"
P=${OURS_PY:-$HOME/jpwork/sdr-venv/bin/python}
export STANZA_RESOURCES_DIR=${STANZA_RESOURCES_DIR:-$HOME/jpwork/stanza_resources_114}
export HF_HUB_OFFLINE=1 SOURCEDRECALL_NOTES=off OURS_PY=$P MEM0_PY=$HOME/jpwork/rg/.venv-judge/bin/python
export FM_JUDGE_OPENAI=http://127.0.0.1:8090/v1 FM_JUDGE_MODEL=qwen3-14b-a8cc1361.gguf
export FM_READER_SAME=1 FM_STRICT=1 FM_JUDGE_QUESTION=1
export FM_CASES=cases_v6.jsonl FM_H2H=$HOME/jpwork/h2h
curl -s -m 10 http://127.0.0.1:8090/v1/models >/dev/null || { echo "reader server on 8090 is down"; exit 1; }
echo '{"_note": "no audit yet", "overrides": []}' > $PWD/no_overrides.json
export FM_OVERRIDES=$PWD/no_overrides.json
R=$PWD/results_v6; rm -rf $R; mkdir -p $R
export FM_RESULTS=$R FM_SCRATCH=$HOME/jpwork/fm_scratch_v6; rm -rf $FM_SCRATCH
echo "== v6 run $(cat ../../COMMIT 2>/dev/null) $(date)"
bash run_all.sh rag ours > $R/run.log 2>&1
for s in agentmemory ai-memory; do $P run_system.py $s >> $R/run.log 2>&1; done
pgrep -fl "agentmemory|bin/iii|ai-memory serve" >/dev/null && echo "warning: tool servers left running"
/usr/bin/python3 answer.py sourcedrecall rag agentmemory ai-memory > $R/answer.log 2>&1
$P score.py > $R/score.log 2>&1
$P v5_parts.py | tee $R/parts.txt
$P fair_summary.py $R | tee $R/summary.txt
echo "== labels on part A (H1)"
$P -c "
import json
with open('$R/cases_v6_A.jsonl','w') as f:
    for l in open('cases_v6.jsonl'):
        if json.loads(l)['subtype'].startswith('A_'): f.write(l)"
$P screen_labels.py $R $R/cases_v6_A.jsonl --counts-only 2>&1 | grep -v Warn | tee $R/labels_A.txt
echo "== advice retrieval (H6)"
ADVICE_SUBTYPE=F_ $P v5_advice.py 2>&1 | grep -v Warn | tee $R/advice.txt
echo "== instructions at session start (H7)"
$P v6_extra.py 2>&1 | grep -v Warn | tee $R/instructions.txt
$P blind_audit.py packet $R audit_results_v6 | tail -1
echo "== v6 done $(date)"
