# student.sh TAG ROWS ITERS : train Qwen3-0.6B on the first ROWS teacher rows, export int4 ONNX, run LoCoMo dev with in-process notes
set -u
TAG=$1; ROWS=$2; ITERS=$3
D=$HOME/jpwork/distil; cd $D
export HF_HOME=$D/hf HF_HUB_OFFLINE=1
head -n $ROWS teacher.jsonl > rows_$TAG.jsonl
venv/bin/python prep.py rows_$TAG.jsonl data_$TAG
venv/bin/python -m mlx_lm lora --model Qwen/Qwen3-0.6B --train --data data_$TAG --fine-tune-type full --mask-prompt \
  --batch-size 4 --iters $ITERS --max-seq-length 4096 --learning-rate 1e-5 --adapter-path ckpt_$TAG \
  --steps-per-report 20 --steps-per-eval 100 --save-every 1000 2>&1 | grep -E "Iter|val|loss" | tail -40
venv/bin/python -m mlx_lm fuse --model Qwen/Qwen3-0.6B --adapter-path ckpt_$TAG --save-path fused_$TAG > /dev/null 2>&1
rm -rf ort_$TAG; $HOME/jpwork/ortgen/venv_build/bin/python -m onnxruntime_genai.models.builder -m Qwen/Qwen3-0.6B -i fused_$TAG -o ort_$TAG \
  -p int4 -e cpu -c $D/hf/cache --extra_options algo_config=k_quant_mixed hf_token=false > build_$TAG.log 2>&1
ls -la ort_$TAG | grep onnx
while pgrep -f notes_sizes.sh > /dev/null; do sleep 60; done
export STANZA_RESOURCES_DIR=$HOME/jpwork/stanza_resources_114
P=$HOME/jpwork/sdr-venv/bin/python; W=$HOME/jpwork/sdr-distil
cd $W/bench/locomo
export RG_REPO=$W LOCOMO_DATA=$HOME/jpwork/locomo10.json LOCOMO_TOP_K=5
export LOCOMO_LLM_BASE=http://127.0.0.1:8090/v1 LOCOMO_LLM_MODEL=qwen3-14b-a8cc1361.gguf
export LOCOMO_SCRATCH=$HOME/jpwork/locomo_stores_student_$TAG
O=results/dev_student_$TAG; rm -rf $O $LOCOMO_SCRATCH; mkdir -p $O
cp $HOME/jpwork/sdr-notes2/bench/locomo/results/dev_notes2/{ctx_rag,ans_rag,ingest_rag}.jsonl $O/
SOURCEDRECALL_NOTES_DIR=$D/ort_$TAG $P retrieve.py sourcedrecall --convs 0-1 --out $O > $O/retrieve.log 2>&1
/usr/bin/python3 answer.py sourcedrecall --out $O > $O/answer.log 2>&1
echo "== student $TAG"; /usr/bin/python3 score.py $O rag sourcedrecall | grep -E "overall|multi-hop|temporal|single-hop|context tokens|model calls"
echo "== student $TAG done $(date)"
