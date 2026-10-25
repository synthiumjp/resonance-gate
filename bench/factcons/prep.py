"""MemoryAgentBench Conflict_Resolution (ai-hyz/MemoryAgentBench, revision
7ea0669, MIT) -> one jsonl per FactConsolidation set in FC_DATA. Needs
pyarrow; the parquet is fetched with huggingface_hub beforehand:

    hf_hub_download("ai-hyz/MemoryAgentBench", "data/Conflict_Resolution-00000-of-00001.parquet",
                    repo_type="dataset", revision="7ea066982b140a19337e17e60d45d4076e042faf")
"""
import json
import os

import pyarrow.parquet as pq

DATA = os.path.expanduser(os.environ.get("FC_DATA", "~/jpwork/mab_data"))
rows = pq.read_table(os.path.join(DATA, "data/Conflict_Resolution-00000-of-00001.parquet")).to_pylist()
ctx = {}
for r in rows:
    name = r["metadata"]["source"]
    with open(os.path.join(DATA, name + ".jsonl"), "w") as fh:
        fh.write(json.dumps({k: r[k] for k in ("context", "questions", "answers")}) + "\n")
    ctx.setdefault(name.rsplit("_", 1)[1], set()).add(r["context"])
    print(name, len(r["questions"]))
for size, c in ctx.items():   # run.py keeps one store per size: sh and mh must share the list
    print(size, "one fact list" if len(c) == 1 else f"{len(c)} DIFFERENT lists")
