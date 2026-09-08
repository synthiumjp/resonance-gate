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
Q=~/rg_private/halumem/qa_rerun2
EVAL=~/rg_private/halumem/official/HaluMem/eval
V=~/rg_private/halumem/official/.venv/bin/python
JUDGE_PY=~/rg/.venv/bin/python
MODEL=/usr/share/ollama/.ollama/models/blobs/sha256-a8cc1361f3145dc01f6d77c6c82c9116b9ffe3c97b34716fe20418455876c40e
LOG="$Q/chain_$(date +%Y%m%d_%H%M)_$MODE.log"
mkdir -p "$Q"

say() { echo "[chain] $*" | tee -a "$LOG"; }

start_judge() {
  if curl -s -m 90 127.0.0.1:8090/v1/models >/dev/null 2>&1; then
    say "judge already up"; return 0
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
  say "$ver judge $(date +%H:%M)"
  ( cd "$EVAL" || exit 1
    RG_PREFIX_NO_THINK=1 PYTHONUNBUFFERED=1 \
      "$V" evaluation.py --frame rgp2 --version "$ver" --user_num 1 \
      > "$Q/judge_$ver.log" 2>&1 )
  say "$ver judge rc=$? $(date +%H:%M)"
}

start_judge || exit 1
case "$MODE" in
  judge)    say "judge only; leaving it up"; exit 0 ;;
  baseline) run qa-rgx4 ~/rg_private/halumem/qa_rgx "RG_INGEST_ALL_TURNS=1"
            run qa-llm3 ~/rg_private/halumem/qa_llm "" ;;
  variants) # extraction-only: RG_SKIP_QA means no answers are generated or
            # judged, so these rows have NO question_answering block -- never
            # compare their QA fields to a baseline row's.
            run qa-rgx4-fb1 ~/rg_private/halumem/qa_rgx "RG_INGEST_ALL_TURNS=1 RG_SKIP_QA=1 RG_SENTENCE_FALLBACK=1"
            run qa-rgx4-fb2 ~/rg_private/halumem/qa_rgx "RG_INGEST_ALL_TURNS=1 RG_SKIP_QA=1 RG_SENTENCE_FALLBACK=2"
            run qa-rgx4-tl  ~/rg_private/halumem/qa_rgx "RG_INGEST_ALL_TURNS=1 RG_SKIP_QA=1 RG_TEXT_LONGEST=1" ;;
  *)        say "unknown mode $MODE"; exit 2 ;;
esac
say "COMPLETE $(date +%H:%M)"
