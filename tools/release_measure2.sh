# Release re-measurement 2 (2026-10-16): every figure the README quotes, on
# ONE commit, with the parser the product installs (the EWT archive,
# stanza_ort). Runs on the Mac (never WSL). From WSL:
#   git archive --format=tar <commit> | ssh <mac> 'rm -rf ~/jpwork/sdr-release-<c> && mkdir -p ~/jpwork/sdr-release-<c> && tar -x -C ~/jpwork/sdr-release-<c>'
#   ssh <mac> 'cd ~/jpwork/sdr-release-<c> && echo <c> > COMMIT && nohup bash tools/release_measure2.sh > ~/jpwork/release6.log 2>&1 &'
# Steps: (1) release_measure.sh -- suite, LoCoMo test default and both notes
# models, LongMemEval-S retrieval, false memory v3/v4/coding/projects;
# (2) the pasted-text held-out sets v11, v12 and the real emails, both
# readers (Qwen3-14B on 8090, Phi-4 started on 8091 and stopped after);
# (3) LongMemEval knowledge-update and temporal answers; (4) HaluMem update
# and QA. Other systems' returns and answers do not change with our commit
# and are copied from the runs the README cites; only sourcedrecall reruns.
# Held-out sets report counts only. The blinded audits' overrides apply
# where an answer is the one they audited (score.py).
set -u
W=$(cd "$(dirname "$0")/.." && pwd)
C=$(cat $W/COMMIT)
P=$HOME/jpwork/sdr-venv/bin/python
J=$HOME/jpwork/rg/.venv-judge/bin/python
Q=http://127.0.0.1:8090/v1
export RGX_PARSER_MODELS=${RGX_PARSER_MODELS:-$HOME/.sourcedrecall/parser-models}
export PYTHONPATH=$W:$W/server STANZA_RESOURCES_DIR=$HOME/jpwork/stanza_resources_114 HF_HUB_OFFLINE=1
echo "== release measure 2 $C $(date), parser $RGX_PARSER_MODELS"
$P -c "import rgx; d = rgx.ort_models_dir(); assert d, 'no parser models'; print('parser', d)" || exit 1
curl -s -m 10 $Q/models | grep -q qwen || { echo "Qwen on 8090 is down"; exit 1; }

echo "== 0. notes models (Hugging Face, the archives setup installs)"
N=$HOME/jpwork/notes_release
for t in small standard; do
  [ -f $N/$t/genai_config.json ] || HF_HUB_OFFLINE=0 SOURCEDRECALL_NOTES_MODELS=$N/$t \
    $P -c "import sys; from sourcedrecall.setup_models import main; sys.exit(main(['--notes', '$t']))" \
    > $N-$t.log 2>&1 || { echo "notes $t failed"; tail -3 $N-$t.log; }
done

echo "== 1. release_measure.sh"
W=$W NOTES_MODELS="small:$N/small standard:$N/standard" bash $W/tools/release_measure.sh

echo "== 2. pasted text, held out (counts only), both readers"
cd $W/bench/false_memory
export SOURCEDRECALL_NOTES=off OURS_PY=$P MEM0_PY=$J
export FM_JUDGE_OPENAI=$Q FM_JUDGE_MODEL=qwen3-14b-a8cc1361.gguf
export FM_READER_SAME=1 FM_SAME_V7=1 FM_STRICT=1 FM_JUDGE_QUESTION=1
unset FM_DISTRACTORS FM_DISTRACTOR_COPIES
nohup $J -m llama_cpp.server --model $HOME/jpwork/models2/phi-4-Q4_K.gguf --n_gpu_layers -1 \
  --n_ctx 16384 --port 8091 --host 127.0.0.1 > $HOME/jpwork/srv_8091.log 2>&1 &
for i in $(seq 1 60); do sleep 5; curl -s -m 3 http://127.0.0.1:8091/v1/models | grep -q phi && break; done
curl -s -m 3 http://127.0.0.1:8091/v1/models | grep -q phi || echo "Phi-4 did not start: its rows are missing"
echo '{"overrides": []}' > $PWD/no_overrides_release.json
for set in v11 v12 realpaste; do
  case $set in
    realpaste) export FM_CASES=cases_real_paste.jsonl; OTHERS="rag";;
    *) export FM_CASES=cases_$set.jsonl; OTHERS="rag agentmemory ai-memory";;
  esac
  for rd in qwen phi4; do
    src=results_$set; [ $rd = phi4 ] && src=results_${set}_phi4
    ov=audit_overrides_$set.json; [ $rd = phi4 ] && ov=audit_overrides_${set}_phi4.json
    [ -f $ov ] || ov=no_overrides_release.json
    R=$PWD/results_release2_${set}_$rd; rm -rf $R; mkdir -p $R
    for o in $OTHERS; do cp $src/raw_$o.jsonl $src/answers_$o.jsonl $R/; done
    if [ $rd = qwen ]; then
      FM_RESULTS=$R FM_SCRATCH=$HOME/jpwork/fm_scratch_release2 bash run_all.sh ours > $R/run.log 2>&1
      rm -rf $HOME/jpwork/fm_scratch_release2
      echo "  $set: $(grep -c '"error"' $R/raw_sourcedrecall.jsonl) of $(wc -l < $R/raw_sourcedrecall.jsonl) scenarios with errors"
      RD=""
    else
      cp $PWD/results_release2_${set}_qwen/raw_sourcedrecall.jsonl $R/
      RD="FM_READER_OPENAI=http://127.0.0.1:8091/v1 FM_READER_MODEL=phi-4"
    fi
    env $RD FM_RESULTS=$R FM_OVERRIDES=$PWD/$ov /usr/bin/python3 answer.py sourcedrecall > $R/answer.log 2>&1
    FM_RESULTS=$R FM_OVERRIDES=$PWD/$ov $P score.py > $R/score.log 2>&1
    echo "-- $set $rd (overrides $ov)"; FM_RESULTS=$R $P v5_parts.py | tee $R/parts.txt
    [ -f ${set}_tests.py ] && FM_RESULTS=$R FM_OVERRIDES=$PWD/$ov $P ${set}_tests.py > $R/tests.txt 2>&1
    # review 2026-10-28 M9: the audit overrides fit the other systems' old
    # answers and only those of sourcedrecall's that did not change, so the
    # counts above mix audited and judge-only verdicts. The same answers,
    # every system judge-only:
    N=$R/noaudit; mkdir -p $N; cp $R/raw_*.jsonl $R/answers_*.jsonl $N/
    [ -f $R/judge_log.jsonl ] && cp $R/judge_log.jsonl $N/
    FM_RESULTS=$N FM_OVERRIDES=$PWD/no_overrides_release.json $P score.py > $N/score.log 2>&1
    echo "-- $set $rd, judge only, no overrides"; FM_RESULTS=$N $P v5_parts.py | tee $N/parts.txt
  done
done
pkill -f "llama_cpp.server.*--port 8091"; echo "  Phi-4 stopped"

echo "== 3. LongMemEval-S knowledge-update and temporal answers"
cd $W/bench/longmemeval
for t in knowledge-update temporal-reasoning; do
  READER=$Q READER_MODEL=qwen3-14b-a8cc1361.gguf LME_DATA=$HOME/jpwork/lme/longmemeval_s_cleaned.json \
    $P lme_answers.py --system sdr --types $t $HOME/jpwork/lme/answers_sdr_${t}_$C.jsonl \
    > $HOME/jpwork/lme/answers_sdr_${t}_$C.log 2>&1 || echo "lme $t failed"
  echo "-- $(tail -1 $HOME/jpwork/lme/answers_sdr_${t}_$C.log)"
done

echo "== 4. HaluMem users 0-1, update and QA"
# both steps run from the harness's eval/ folder: its llms.py reads the .env there
cd $HOME/jpwork/rg_private/halumem/official/HaluMem/eval
HALUMEM_SCRATCH=$HOME/jpwork/halumem_scratch_release2 $P $W/experiments/p2/halumem_official/eval_sdr.py \
  --system sdr --version sdr-$C --users 0,1 > $HOME/jpwork/halumem_release2_store.log 2>&1 || echo "halumem store failed"
$P evaluation_uqa.py --frame rgp2 --version sdr-$C --user_num 2 > $HOME/jpwork/halumem_release2_uqa.log 2>&1 || echo "uqa failed"
/usr/bin/python3 -c "
import json; r=json.load(open('results/rgp2-sdr-$C/rgp2_eval_stat_result_uqa.json'))['overall_score']
for k in ('memory_update', 'question_answering'): print(k, json.dumps(r[k]))"
echo "== 5. LoCoMo strict judge on sourcedrecall's answers"
# 2026-10-21: done by hand for 53e0d9c (~/jpwork/mh/strict_release.sh); Mem0's
# and plain retrieval's strict verdicts do not change and are copied
cd $W/bench/locomo
for x in default small standard; do
  D=results/release_test_$x
  [ -d $D ] || continue
  LOCOMO_LLM_BASE=$Q LOCOMO_LLM_MODEL=qwen3-14b-a8cc1361.gguf LOCOMO_JUDGE=strict \
    /usr/bin/python3 rejudge.py $D sourcedrecall > $D/rejudge_strict.log 2>&1 || { echo "strict rejudge $x failed"; continue; }
  for s in mem0 rag; do
    cp results/strict_release_test_default/ans_${s}_strict.jsonl $D/
    [ -e $D/ctx_${s}_strict.jsonl ] || ln -s ctx_$s.jsonl $D/ctx_${s}_strict.jsonl
  done
  for au in "" $W/bench/locomo/results/locomo_audit_errors.json; do
    echo "-- strict $x ${au:+without the audit wrong gold answers}"
    LOCOMO_AUDIT=$au LOCOMO_JUDGE= /usr/bin/python3 score.py $D sourcedrecall_strict mem0_strict rag_strict | grep -E "^\| (overall|1 multi|2 temporal|3 open|4 single)"
  done
done

echo "== release measure 2 done $(date)"
