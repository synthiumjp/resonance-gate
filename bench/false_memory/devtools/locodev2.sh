# LoCoMo dev on sdr-dev16 (the cut with the same-conversation rule) at 0.5;
# settings as tools/release_measure.sh (top-k 5, notes off); lenient judge,
# then the strict judge
set -u
W=$HOME/jpwork/sdr-dev16
P=$HOME/jpwork/sdr-venv/bin/python
export STANZA_RESOURCES_DIR=$HOME/jpwork/stanza_resources_114 HF_HUB_OFFLINE=1 SOURCEDRECALL_NOTES=off
export RG_REPO=$W LOCOMO_DATA=$HOME/jpwork/locomo10.json LOCOMO_TOP_K=5
export LOCOMO_LLM_BASE=http://127.0.0.1:8090/v1 LOCOMO_LLM_MODEL=qwen3-14b-a8cc1361.gguf
cd $W/bench/locomo
for v in 0.5; do
  O=results/dev_cut$v; rm -rf $O; mkdir -p $O
  for f in ctx_rag ans_rag ingest_rag ctx_mem0 ans_mem0 ingest_mem0; do cp $HOME/jpwork/sdr/bench/locomo/results/dev/$f.jsonl $O/; done
  export LOCOMO_SCRATCH=$HOME/jpwork/locomo_stores_dev_cut$v; rm -rf $LOCOMO_SCRATCH
  RG_MSG_CUT=$v $P retrieve.py sourcedrecall --convs 0-1 --out $O > $O/retrieve.log 2>&1
  /usr/bin/python3 answer.py sourcedrecall --out $O > $O/answer.log 2>&1
  echo "-- locomo dev cut $v"; /usr/bin/python3 score.py $O sourcedrecall mem0 rag | tee $O/score.md | grep -E "overall|multi-hop|temporal|single-hop|open|context tokens"
done
echo "locodev2 done"
