"""E5.1 leak pass driver: characterise the local judge on the 60-item
labelled set (per-class breakdown), then judge the 288 candidate outputs
emitted by run_e51.py, with per-surface leak rates. Writes:
  e5/leak_v3_characterisation.json
  e5/e51_leak_judged.jsonl  (+ returns the by-surface summary)

Judge is pinned by the --model string and echoed into both outputs (the
leak rate is meaningless without the grader pinned — see leak_v3 docstring).

Usage: python e5/run_leak_v3.py [--model ollama:qwen3:14b] [--char-only]
"""

import argparse
import json
import os
import time
from collections import defaultdict

import _env  # noqa: F401  (path setup)

import leak_v3

HERE = os.path.dirname(os.path.abspath(__file__))
OLLAMA_MODELS = os.environ.get(
    "OLLAMA_MODELS", "/usr/share/ollama/.ollama/models")


def resolve_model(spec):
    """Turn an ollama tag ('qwen3:14b') into a GPU llama-cpp backend string
    ('llamacpp:<gguf blob path>'). ollama 0.15.2 here has no ROCm runner and
    falls back to CPU (~20s/item); llama-cpp-python uses the working
    hipBLAS/gfx1100 build (~1s/item), so E5.1 judges via the downloaded GGUF
    blob directly. Pass a spec already prefixed llamacpp:/ollama:/claude-*
    to bypass resolution."""
    if ":" in spec and spec.split(":", 1)[0] in ("llamacpp", "ollama") \
            or spec.startswith("claude") or spec.startswith("local:"):
        return spec
    name, _, tag = spec.partition(":")
    tag = tag or "latest"
    manifest = os.path.join(OLLAMA_MODELS, "manifests",
                            "registry.ollama.ai", "library", name, tag)
    with open(manifest) as f:
        m = json.load(f)
    digest = next(l["digest"] for l in m["layers"]
                  if l["mediaType"].endswith(".model"))
    blob = os.path.join(OLLAMA_MODELS, "blobs", digest.replace(":", "-"))
    return f"llamacpp:{blob}"
CANDIDATES = os.path.join(HERE, "e51_leak_candidates.jsonl")
CHAR_OUT = os.path.join(HERE, "leak_v3_characterisation.json")
JUDGED_OUT = os.path.join(HERE, "e51_leak_judged.jsonl")


def characterise(model):
    res = leak_v3.characterise_judge(model, leak_v3.DEFAULT_CHARSET)
    by_class = defaultdict(lambda: {"n": 0, "correct": 0})
    parse_err = 0
    for it in res["per_item"]:
        c = by_class[it["class"]]
        c["n"] += 1
        c["correct"] += int(it["pred"] == it["label"])
        if it["verdict"].get("parse_error"):
            parse_err += 1
    res["by_class"] = {k: v for k, v in by_class.items()}
    res["parse_errors"] = parse_err
    with open(CHAR_OUT, "w") as f:
        json.dump({k: v for k, v in res.items() if k != "per_item"}, f, indent=2)
    # keep full per-item alongside for audit
    with open(os.path.join(HERE, "leak_v3_char_peritem.jsonl"), "w") as f:
        for it in res["per_item"]:
            f.write(json.dumps(it) + "\n")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen3:14b")
    ap.add_argument("--char-only", action="store_true")
    args = ap.parse_args()

    args.judge_tag = args.model            # human-readable, for the report
    args.model = resolve_model(args.model)
    print(f"[leak_v3] judge: {args.judge_tag}  ->  {args.model}")
    t0 = time.time()
    ch = characterise(args.model)
    print(f"[leak_v3] characterisation ({time.time()-t0:.0f}s): "
          f"precision={ch['precision']:.3f} recall={ch['recall']:.3f} "
          f"tp={ch['tp']} fp={ch['fp']} fn={ch['fn']} tn={ch['tn']} "
          f"parse_errors={ch['parse_errors']}")
    for cls, v in sorted(ch["by_class"].items()):
        print(f"    {cls:16s} {v['correct']}/{v['n']} correct")

    if args.char_only:
        return

    t1 = time.time()
    summary = leak_v3.run_leak_pass(CANDIDATES, args.model, JUDGED_OUT)
    print(f"[leak_v3] leak pass over {summary['n']} outputs "
          f"({time.time()-t1:.0f}s): {summary['n_leak']} leaks = "
          f"{summary['rate']:.4f}")
    for surf, v in sorted(summary["by_surface"].items()):
        print(f"    {surf:28s} {v['n_leak']}/{v['n']} = {v['rate']:.3f}")
    with open(os.path.join(HERE, "e51_leak_summary.json"), "w") as f:
        json.dump({"judge": args.judge_tag, "backend": args.model,
                   "characterisation":
                   {k: ch[k] for k in ("precision", "recall", "tp", "fp",
                                       "fn", "tn", "parse_errors", "by_class")},
                   "leak": summary}, f, indent=2)


if __name__ == "__main__":
    main()
