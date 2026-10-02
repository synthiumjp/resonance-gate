#!/bin/bash
# One judged run, start to finish: judge server, arms, results.
#
# 2026-09-09. Written after two runs were lost to things this script now
# handles: the judge server does not survive a reboot (it is started here and
# checked, not assumed), and `eval_rgp2.py` is reached through a symlink so
# the harness-local `llms` module is only importable from the eval directory
# (that is why every arm cd's there).
#
#   tools/run_judged.sh variants     fb1, fb2 and text-longest, extraction-only
#   tools/run_judged.sh baseline     the rgx and llm baseline rows, full
#   tools/run_judged.sh judge        just start the judge server and wait
#
# Every arm is one flag against the same cache. Verdicts are cached
# (RG_JUDGE_CACHE, see experiments/p2/halumem_official/llms.py), so a rerun
# after a crash replays what it already paid for and a variant only pays for
# the records it changed.
set -u
MODE="${1:-variants}"
# Every location is overridable, so the same script runs on WSL (defaults)
# and the Mac Studio (tools/run_judged_mac.env sets the Mac values).
Q=${RG_Q:-~/rg_private/halumem/qa_rerun2}
EVAL=${RG_EVAL:-~/rg_private/halumem/official/HaluMem/eval}
V=${RG_PY:-~/rg_private/halumem/official/.venv/bin/python}
JUDGE_PY=${RG_JUDGE_PY:-~/rg/.venv/bin/python}
MODEL=${RG_MODEL:-/usr/share/ollama/.ollama/models/blobs/sha256-a8cc1361f3145dc01f6d77c6c82c9116b9ffe3c97b34716fe20418455876c40e}
RG=${RG_HOME:-/home/jp/rg}
# The judge's identity travels WITH the GGUF that serves it. The verdict
# cache keys on both (llms.py), so changing MODEL above changes the key and a
# second judge can never replay the first one's verdicts. RG_JUDGE_SUFFIX
# names the BACKEND: Metal and ROCm are not guaranteed to give identical
# verdicts at temperature 0, so a Mac verdict is never replayed on WSL or
# vice versa.
export OPENAI_MODEL=qwen3:14b
export RG_JUDGE_ID="sha256-$(basename "$MODEL" | grep -oE '[0-9a-f]{64}' || basename "$MODEL")${RG_JUDGE_SUFFIX:-}"
QA_RGX=${RG_QA_RGX:-~/rg_private/halumem/qa_rgx}
QA_LLM=${RG_QA_LLM:-~/rg_private/halumem/qa_llm}
LOG="$Q/chain_$(date +%Y%m%d_%H%M)_$MODE.log"
mkdir -p "$Q"

say() { echo "[chain] $*" | tee -a "$LOG"; }

start_judge() {
  local served
  served=$(curl -s -m 90 127.0.0.1:8090/v1/models 2>/dev/null)
  if [ -n "$served" ]; then
    # review 2026-10-02: "something answers on :8090" is not "our judge is up"
    if echo "$served" | grep -q "$(basename "$MODEL")"; then
      say "judge already up ($RG_JUDGE_ID)"; return 0
    fi
    say "A DIFFERENT MODEL is serving :8090 -- refusing to judge with it"
    say "served: $(echo "$served" | head -c 200)"
    return 1
  fi
  say "starting judge $(date +%H:%M)"
  nohup "$JUDGE_PY" -m llama_cpp.server --model "$MODEL" \
    --n_gpu_layers -1 --n_ctx 16384 --port 8090 --host 127.0.0.1 \
    --chat_format chatml > "$Q/judge_server.log" 2>&1 &
  for _ in $(seq 1 60); do
    sleep 10
    curl -s -m 30 127.0.0.1:8090/v1/models >/dev/null 2>&1 && { say "judge up"; return 0; }
  done
  say "JUDGE FAILED TO START -- see $Q/judge_server.log"; return 1
}

# run <version> <cache dir> <extra env>
run() {
  local ver=$1 dir=$2 extra=$3
  say "$ver compose $(date +%H:%M) cache $(wc -l < "$dir/cache_u0_v5.jsonl")"
  ( cd "$EVAL" || exit 1
    env RG_EXTRACT_V5=1 RG_PREFIX_NO_THINK=1 RG_RETRIEVE_V3=1 $extra \
        OPENAI_BASE_URL=http://localhost:8090/v1 PYTHONUNBUFFERED=1 \
        "$V" eval_rgp2.py --version "$ver" --users 0 --cache_dir "$dir" \
        > "$Q/compose_$ver.log" 2>&1 )
  local rc=$?
  say "$ver compose rc=$rc"
  [ $rc -ne 0 ] && { say "$ver compose FAILED -- not judging"; return 1; }
  # review 2026-10-02: evaluation.py skips any user with a checkpoint in
  # tmp2/ and re-aggregates it, so judging a re-composed version would have
  # reported the OLD verdicts as fresh. The per-verdict cache (llms.py) makes
  # a clean slate cheap: everything unchanged replays from the cache.
  rm -rf "$EVAL/results/rgp2-$ver/tmp2" "$EVAL/results/rgp2-$ver/rgp2_eval_stat_result.json"
  say "$ver judge $(date +%H:%M)"
  ( cd "$EVAL" || exit 1
    RG_PREFIX_NO_THINK=1 PYTHONUNBUFFERED=1 \
      "$V" evaluation.py --frame rgp2 --version "$ver" --user_num 1 \
      > "$Q/judge_$ver.log" 2>&1 )
  local jrc=$?
  say "$ver judge rc=$jrc $(date +%H:%M)"
  # review 2026-10-02: a dead judge records None scores and still exits 0.
  if ! python3 "$RG/tools/check_judged.py" "$ver" >> "$LOG" 2>&1 || [ $jrc -ne 0 ]; then
    say "$ver judge FAILED -- see check_judged output above"
    return 1
  fi
}

start_judge || exit 1
case "$MODE" in
  judge)    say "judge only; leaving it up"; exit 0 ;;
  baseline) run qa-rgx4 "$QA_RGX" "RG_INGEST_ALL_TURNS=1"
            run qa-llm3 "$QA_LLM" "" ;;
  variants) # extraction-only: RG_SKIP_QA means no answers are generated or
            # judged, so these rows have NO question_answering block -- never
            # compare their QA fields to a baseline row's.
            run qa-rgx4-fb1 "$QA_RGX" "RG_INGEST_ALL_TURNS=1 RG_SKIP_QA=1 RG_SENTENCE_FALLBACK=1"
            run qa-rgx4-fb2 "$QA_RGX" "RG_INGEST_ALL_TURNS=1 RG_SKIP_QA=1 RG_SENTENCE_FALLBACK=2"
            run qa-rgx4-tl  "$QA_RGX" "RG_INGEST_ALL_TURNS=1 RG_SKIP_QA=1 RG_TEXT_LONGEST=1" ;;
  extraction) # the SAME-JUDGE comparison set: the baseline and the three
            # variants, all extraction-only, all judged by one backend. Run
            # this whenever the judge host changes (2026-10-02: the Mac).
            run "qa-rgx4-x${RG_TAG:-}"   "$QA_RGX" "RG_INGEST_ALL_TURNS=1 RG_SKIP_QA=1"
            run "qa-rgx4-fb1${RG_TAG:-}" "$QA_RGX" "RG_INGEST_ALL_TURNS=1 RG_SKIP_QA=1 RG_SENTENCE_FALLBACK=1"
            run "qa-rgx4-fb2${RG_TAG:-}" "$QA_RGX" "RG_INGEST_ALL_TURNS=1 RG_SKIP_QA=1 RG_SENTENCE_FALLBACK=2"
            run "qa-rgx4-tl${RG_TAG:-}"  "$QA_RGX" "RG_INGEST_ALL_TURNS=1 RG_SKIP_QA=1 RG_TEXT_LONGEST=1" ;;
  *)        say "unknown mode $MODE"; exit 2 ;;
esac
say "COMPLETE $(date +%H:%M)"
