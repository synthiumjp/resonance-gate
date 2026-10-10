# Held-out v9, one run (docs/PREREG_HELDOUT_V9.md), on the Mac from a tree of
# the frozen commit. The fair protocol: every system's returns to the same
# reader with the same instruction (v7's, FM_SAME_V7=1), the judge given the
# question, strict scoring; the blinded audit follows (blind_audit.py).
# Counts only.
set -u
cd "$(dirname "$0")"
P=${OURS_PY:-$HOME/jpwork/sdr-venv/bin/python}
export STANZA_RESOURCES_DIR=${STANZA_RESOURCES_DIR:-$HOME/jpwork/stanza_resources_114}
export HF_HUB_OFFLINE=1 SOURCEDRECALL_NOTES=off OURS_PY=$P MEM0_PY=$HOME/jpwork/rg/.venv-judge/bin/python
export FM_JUDGE_OPENAI=http://127.0.0.1:8090/v1 FM_JUDGE_MODEL=qwen3-14b-a8cc1361.gguf
export FM_READER_SAME=1 FM_SAME_V7=1 FM_STRICT=1 FM_JUDGE_QUESTION=1
export FM_CASES=cases_v9.jsonl FM_H2H=$HOME/jpwork/h2h
curl -s -m 10 http://127.0.0.1:8090/v1/models >/dev/null || { echo "reader server on 8090 is down"; exit 1; }
echo '{"_note": "no audit yet", "overrides": []}' > $PWD/no_overrides.json
export FM_OVERRIDES=$PWD/no_overrides.json
R=$PWD/results_v9; rm -rf $R; mkdir -p $R
export FM_RESULTS=$R FM_SCRATCH=$HOME/jpwork/fm_scratch_v9; rm -rf $FM_SCRATCH
echo "== v9 run $(cat ../../COMMIT 2>/dev/null) $(date)"
bash run_all.sh rag ours > $R/run.log 2>&1
# the competitors' adapters need their scratch inside FM_H2H (learned in v6)
mkdir -p $FM_H2H/scratch_v9
for s in agentmemory ai-memory; do FM_SCRATCH=$FM_H2H/scratch_v9 $P run_system.py $s >> $R/run.log 2>&1; done
pgrep -fl "agentmemory|bin/iii|ai-memory serve" >/dev/null && echo "warning: tool servers left running"
for s in rag sourcedrecall agentmemory ai-memory; do
  n=$(grep -c '"error"' $R/raw_$s.jsonl 2>/dev/null || echo 0)
  echo "$s: $(wc -l < $R/raw_$s.jsonl 2>/dev/null) scenarios, $n with errors"
done
/usr/bin/python3 answer.py sourcedrecall rag agentmemory ai-memory > $R/answer.log 2>&1
$P score.py > $R/score.log 2>&1
$P v5_parts.py | tee $R/parts.txt
$P v9_tests.py | tee $R/tests.txt
$P blind_audit.py packet $R audit_results_v9 | tail -1
echo "== v9 done $(date)"
