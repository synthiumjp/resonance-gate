#!/bin/bash
# S5 -- JUDGED A/B of all-turns ingestion. The one extraction change the
# ledger reserves the judge budget for (docs/EXPERIMENT_LEDGER.md sections 5a/7).
#
# Entry 194 measured all-turns at +14.01pt recall on the token-overlap proxy.
# Entry 202 then showed that proxy's 0.5 threshold sits on the mode of the
# distribution, so it can support PAIRED comparisons but no absolute figure.
# This run replaces the proxy with the official judge on the same comparison.
#
# Arms, user 10 only (the only user with assistant-turn extractions cached),
# everything else held fixed -- one variable:
#     base   user turns only          (RG_INGEST_ALL_TURNS unset)
#     all    user + assistant turns   (RG_INGEST_ALL_TURNS=1)
# Held fixed in BOTH: RG_EXTRACT_V5, RG_EMIT_ONCE, RG_RETRIEVE_V3, no gate,
# no RG_ARTIFACT_NO_TIER. Read the result as "what all-turns buys GIVEN that
# stack", not as an absolute score.
#
# Predicted judge calls (counted offline, exact):
#     base 1822 = 1014 accuracy + 536 integrity + 135 update + 137 QA
#     all  2398 = 1590 accuracy + 536 integrity + 135 update + 137 QA
#
# Checkpointing: stage 2 is chunked to ~9 sessions per line (s5_chunk.py), so
# the judge writes a tmp2/ checkpoint every ~350 calls instead of once at the
# very end. Re-running the script resumes from those checkpoints.
set -u

SP=/tmp/claude-1000/-home-jp-rg/320688fb-20b4-45ea-b1e7-d0fbb0e3ca6c/scratchpad/s5
O=~/rg_private/halumem/official
EV=$O/HaluMem/eval
PY=$O/.venv/bin/python
QWEN=/usr/share/ollama/.ollama/models/blobs/sha256-a8cc1361f3145dc01f6d77c6c82c9116b9ffe3c97b34716fe20418455876c40e
PER=9

mkdir -p $SP

# --- server: verify ROCm, never start a CPU run (entry 107 rule) -----------
if ! curl -s -m3 http://localhost:8090/v1/models >/dev/null 2>&1; then
  nohup /home/jp/rg/.venv/bin/python -m llama_cpp.server --model "$QWEN" \
    --n_gpu_layers -1 --n_ctx 16384 --port 8090 --host 127.0.0.1 \
    --chat_format chatml >> $SP/server.log 2>&1 & disown
  until curl -s -m3 http://localhost:8090/v1/models >/dev/null 2>&1; do sleep 4; done
fi
if ! grep -qE "found 1 ROCm devices" $SP/server.log 2>/dev/null; then
  echo "ABORT: no ROCm banner in $SP/server.log -- refusing a CPU judge run"
  exit 1
fi
echo "[$(date +%H:%M)] server verified on GPU"

# --- stage 1: build the extraction + QA artifact for each arm --------------
for ARM in base all; do
  OUT=$EV/results/rgp2-s5-$ARM/rgp2_eval_results.jsonl
  if [ -s "$OUT" ]; then
    echo "[$(date +%H:%M)] stage1 $ARM already built, skipping"
    continue
  fi
  echo "[$(date +%H:%M)] stage1 $ARM: composing artifact"
  ALLT=0; [ "$ARM" = "all" ] && ALLT=1
  cd $EV && RG_EXTRACT_V5=1 RG_PREFIX_NO_THINK=1 RG_RETRIEVE_V3=1 \
    RG_EMIT_ONCE=1 RG_INGEST_ALL_TURNS=$ALLT \
    OPENAI_BASE_URL=http://localhost:8090/v1 \
    $PY eval_rgp2.py --version s5-$ARM --users 10 --cache_dir $SP/cache \
    > $SP/stage1_$ARM.log 2>&1 || { echo "stage1 $ARM FAILED"; exit 1; }
done

# --- preflight: the arms must actually differ ------------------------------
# A silent env-var failure (the .env line-32 incident, entry 181) would make
# both arms identical and waste the entire judge budget. Assert before paying.
$PY - <<'EOF' || exit 1
import json, os, sys
EV = os.path.expanduser("~/rg_private/halumem/official/HaluMem/eval")
n = {}
for arm in ("base", "all"):
    p = f"{EV}/results/rgp2-s5-{arm}/rgp2_eval_results.jsonl"
    u = json.loads(open(p).readline())
    n[arm] = sum(len(s.get("extracted_memories", [])) for s in u["sessions"])
print(f"PREFLIGHT emissions: base={n['base']} all={n['all']}")
exp = {"base": 1014, "all": 1590}
if n != exp:
    print(f"ABORT: emission counts {n} != offline prediction {exp} -- "
          "the arms are not the configuration that was costed")
    sys.exit(1)
print("PREFLIGHT OK: arms differ as predicted")
EOF

# --- stage 2: chunk, then judge --------------------------------------------
for ARM in base all; do
  SRC=$EV/results/rgp2-s5-$ARM/rgp2_eval_results.jsonl
  JDIR=$EV/results/rgp2-s5-$ARM-j
  mkdir -p $JDIR
  cd /home/jp/rg/experiments/p2 && python3 s5_chunk.py "$SRC" \
    "$JDIR/rgp2_eval_results.jsonl" --per $PER || exit 1
  NCH=$(wc -l < "$JDIR/rgp2_eval_results.jsonl")
  echo "[$(date +%H:%M)] stage2 $ARM: judging $NCH chunks"
  cd $EV && RG_PREFIX_NO_THINK=1 \
    $PY evaluation.py --frame rgp2 --version s5-$ARM-j --user_num $NCH \
    >> $SP/stage2_$ARM.log 2>&1 || { echo "stage2 $ARM FAILED"; exit 1; }
  echo "[$(date +%H:%M)] stage2 $ARM done"
done

touch $SP/S5_DONE
echo "[$(date +%H:%M)] S5 COMPLETE"
