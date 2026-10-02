#!/bin/bash
# Quality watcher for a judged chain (tools/run_judged.sh).
#
#   tools/watch_chain.sh <chain log> "<version> <version> ..."
#
# Emits one line per phase change or anomaly and exits on COMPLETE, on a
# failed compose, or on a real judge outage. Two things it has already been
# taught, both from real incidents:
#   * the judge server is single-threaded and blocks for a minute at a time
#     during a generation, so a health probe needs a long timeout and two
#     consecutive misses before it cries outage (a 5s probe cried wolf);
#   * the compose log only prints every 25 questions, so silence there is not
#     evidence of a stall -- the judge server's own log is the liveness
#     signal.
# It is deliberately NOT a liveness watcher: the sentinel's lesson is that a
# process can be alive and producing garbage.
set -u
Q=~/rg_private/halumem/qa_rerun2
R=~/rg_private/halumem/official/HaluMem/eval/results
CHAIN="${1:?usage: watch_chain.sh <chain log> \"<versions>\"}"
VERSIONS="${2:-}"
STALL=$((40 * 60))
seen=0
jmiss=0
START=""

while true; do
  [ -f "$CHAIN" ] || { sleep 30; continue; }
  # a FIXED reference time. The first version compared each log to the chain
  # log's mtime, which every `say` refreshes -- so a traceback written before
  # the latest chain line was never seen (review 2026-10-02).
  [ -n "$START" ] || START=$(( $(stat -c %Y "$CHAIN") - 120 ))
  n=$(wc -l < "$CHAIN")
  if [ "$n" -gt "$seen" ]; then sed -n "$((seen + 1)),${n}p" "$CHAIN"; seen=$n; fi

  if grep -q "COMPLETE" "$CHAIN"; then
    for v in $VERSIONS; do
      f="$R/rgp2-$v/rgp2_eval_stat_result.json"
      [ -f "$f" ] && python3 - "$f" "$v" <<'PY'
import json, sys
d = json.load(open(sys.argv[1])).get("overall_score", {})
qa, ex, up = (d.get("question_answering", {}), d.get("memory_integrity", {}),
              d.get("memory_update", {}))
acc = d.get("memory_accuracy", {})
print(f"RESULT {sys.argv[2]}: "
      f"recall={ex.get('recall(all)')} weighted={ex.get('weighted_recall(all)')} "
      f"target_acc={acc.get('target_accuracy(all)')} "
      f"interference={acc.get('interference_accuracy(all)')} "
      f"update_correct={up.get('correct_update_memory_ratio(all)')} "
      f"qa_correct={qa.get('correct_qa_ratio(all)')}")
PY
    done
    echo "DONE chain complete"; exit 0
  fi

  if grep -q "FAILED" "$CHAIN"; then
    echo "ANOMALY: an arm reported FAILED (compose or judge)"
    tail -5 "$Q"/compose_*.log 2>/dev/null | cut -c1-200
    exit 2
  fi

  for f in "$Q"/compose_*.log "$Q"/judge_*.log; do
    [ -f "$f" ] || continue
    # only logs written since this chain started
    [ "$(stat -c %Y "$f")" -ge "$START" ] || continue
    if grep -q "Traceback" "$f"; then
      echo "ANOMALY: Traceback in $(basename "$f")"
      grep -A6 Traceback "$f" | tail -8 | cut -c1-200
      exit 2
    fi
  done

  newest=$(ls -t "$Q"/compose_*.log "$Q"/judge_*.log "$Q"/judge_server.log 2>/dev/null | head -1)
  if [ -n "$newest" ]; then
    age=$(( $(date +%s) - $(stat -c %Y "$newest") ))
    if [ "$age" -gt "$STALL" ]; then
      echo "ANOMALY: $(basename "$newest") silent for $((age / 60)) min"
      tail -3 "$newest" | cut -c1-200
      exit 2
    fi
  fi

  if curl -s -m 90 127.0.0.1:8090/v1/models >/dev/null 2>&1; then jmiss=0; else jmiss=$((jmiss + 1)); fi
  if [ "$jmiss" -ge 2 ]; then echo "ANOMALY: judge :8090 down twice in a row"; exit 2; fi

  sleep 600
done
