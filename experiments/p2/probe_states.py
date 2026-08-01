"""Dump last-token hidden states (every layer) of Qwen3.5-4B-4bit reading
(evidence, question) pairs -- training data for the evidence-sufficiency
probe. Architecture-agnostic: wraps each transformer layer to record its
output, then runs the model's own forward. Output: one .npz per split with
states[n_rows, n_layers, hidden] float16 + labels.
"""
import json
import sys

import mlx.core as mx
import numpy as np
from mlx_lm import load

PROMPT = ("MEMORIES:\n{context}\n\nQUESTION: {question}\n\n"
          "Can the question be answered from the memories above?")


def find_layers(root):
    """Walk the module tree for the longest list of modules (the layer stack)."""
    best = None
    stack = [root]
    seen = set()
    while stack:
        mod = stack.pop()
        if id(mod) in seen:
            continue
        seen.add(id(mod))
        for name, child in mod.children().items():
            if isinstance(child, list):
                mods = [c for c in child if hasattr(c, "__call__")]
                if len(mods) > 8 and (best is None or len(mods) > len(best)):
                    best = mods
                for c in mods:
                    stack.append(c)
            elif hasattr(child, "children"):
                stack.append(child)
    return best


class Recorder:
    """Class-level patch: dunder __call__ is looked up on the TYPE, so an
    instance-attribute wrapper never fires. Patch each distinct layer class
    once (hybrid archs mix block classes); record only tracked instances."""

    def __init__(self, layers):
        self.outs = []
        self.tracked = {id(l) for l in layers}
        rec = self
        for cls in {type(l) for l in layers}:
            orig = cls.__call__

            def make(orig):
                def wrapped(slf, *a, **k):
                    out = orig(slf, *a, **k)
                    if id(slf) in rec.tracked:
                        h = out[0] if isinstance(out, tuple) else out
                        if getattr(h, "ndim", 0) == 3:
                            rec.outs.append(h[:, -1, :])
                    return out
                return wrapped
            cls.__call__ = make(orig)


CHUNK = 100


def main(split):
    import os
    import resource
    model, tok = load("mlx-community/Qwen3.5-4B-4bit")
    layers = find_layers(model)
    print(f"{split}: wrapping {len(layers)} layers", flush=True)
    rec = Recorder(layers)
    rows = [json.loads(l) for l in open(f"gate_{split}.jsonl")]
    n_chunks = (len(rows) + CHUNK - 1) // CHUNK
    for c in range(n_chunks):
        part = f"states_{split}_part{c}.npz"
        if os.path.exists(part):
            continue                     # resumable: a kill loses <=1 chunk
        states, labels = [], []
        for r in rows[c * CHUNK:(c + 1) * CHUNK]:
            text = PROMPT.format(context=r["context"], question=r["question"])
            ids = tok.encode(text)[-4096:]
            rec.outs = []
            _ = model(mx.array([ids]))
            mx.eval([o for o in rec.outs])
            states.append(np.stack([np.array(o.astype(mx.float16))[0]
                                    for o in rec.outs]))
            labels.append(r["label"])
            mx.clear_cache()             # Metal buffer cache balloons otherwise
        np.savez_compressed(part, states=np.stack(states),
                            labels=np.array(labels))
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**30
        print(f"  chunk {c+1}/{n_chunks} saved  rss={rss:.1f}GiB", flush=True)
    parts = [np.load(f"states_{split}_part{c}.npz") for c in range(n_chunks)]
    np.savez_compressed(f"states_{split}.npz",
                        states=np.concatenate([p["states"] for p in parts]),
                        labels=np.concatenate([p["labels"] for p in parts]))
    print(f"saved states_{split}.npz", flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
