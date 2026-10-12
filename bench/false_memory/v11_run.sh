# Held-out v11, one run (docs/PREREG_HELDOUT_V11.md), on the Mac from a tree of
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
export FM_CASES=cases_v11.jsonl FM_H2H=$HOME/jpwork/h2h
curl -s -m 10 http://127.0.0.1:8090/v1/models >/dev/null || { echo "reader server on 8090 is down"; exit 1; }
# the second reader (Phi-4, microsoft/phi-4-gguf phi-4-Q4_K.gguf, sha256
# 5652b9be0ea4ae2842130d04fe31bc869fcb99a2b7106c53b4e754a343fd688f, llama_cpp.server
# on 8091 with the GGUF's chat template)
curl -s -m 10 http://127.0.0.1:8091/v1/models | grep -q phi || { echo "second reader on 8091 is down"; exit 1; }
echo '{"_note": "no audit yet", "overrides": []}' > $PWD/no_overrides.json
export FM_OVERRIDES=$PWD/no_overrides.json
R=$PWD/results_v11; rm -rf $R; mkdir -p $R
export FM_RESULTS=$R FM_SCRATCH=$HOME/jpwork/fm_scratch_v11; rm -rf $FM_SCRATCH
echo "== v11 run $(cat ../../COMMIT 2>/dev/null) $(date)"
bash run_all.sh rag ours > $R/run.log 2>&1
# the competitors' adapters need their scratch inside FM_H2H (learned in v6)
mkdir -p $FM_H2H/scratch_v11
for s in agentmemory ai-memory; do FM_SCRATCH=$FM_H2H/scratch_v11 $P run_system.py $s >> $R/run.log 2>&1; done
pgrep -fl "agentmemory|bin/iii|ai-memory serve" >/dev/null && echo "warning: tool servers left running"
for s in rag sourcedrecall agentmemory ai-memory; do
  n=$(grep -c '"error"' $R/raw_$s.jsonl 2>/dev/null || echo 0)
  echo "$s: $(wc -l < $R/raw_$s.jsonl 2>/dev/null) scenarios, $n with errors"
done
/usr/bin/python3 answer.py sourcedrecall rag agentmemory ai-memory > $R/answer.log 2>&1
$P score.py > $R/score.log 2>&1
$P v5_parts.py | tee $R/parts.txt
$P v11_tests.py | tee $R/tests.txt
# reported, not tested: sourcedrecall's returns without its rules paragraph
# (the "[pasted in by ...]" markers stay in the lines), Qwen3-14B reader;
# the judge's verdicts, not audited
R3=$PWD/results_v11_norules; rm -rf $R3; mkdir -p $R3
cp $R/raw_*.jsonl $R3/; for s in rag agentmemory ai-memory; do cp $R/answers_$s.jsonl $R3/; done
FM_RESULTS=$R3 FM_OURS_RULES=0 /usr/bin/python3 answer.py sourcedrecall > $R3/answer.log 2>&1
FM_RESULTS=$R3 $P score.py > $R3/score.log 2>&1
FM_RESULTS=$R3 $P v11_tests.py | tee $R3/tests.txt
# the same retrievals read by the second reader; the judge stays Qwen3-14B
R2=$PWD/results_v11_phi4; rm -rf $R2; mkdir -p $R2
cp $R/raw_*.jsonl $R2/
FM_RESULTS=$R2 FM_READER_OPENAI=http://127.0.0.1:8091/v1 FM_READER_MODEL=phi-4 \
  /usr/bin/python3 answer.py sourcedrecall rag agentmemory ai-memory > $R2/answer.log 2>&1
FM_RESULTS=$R2 $P score.py > $R2/score.log 2>&1
FM_RESULTS=$R2 $P v11_tests.py | tee $R2/tests.txt
$P blind_audit.py packet $R audit_results_v11 | tail -1
$P blind_audit.py packet $R2 audit_results_v11_phi4 | tail -1
echo "== v11 done $(date)"
