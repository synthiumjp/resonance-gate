"""The mouth: SmolLM3-3B Q4, frozen, via llama-cpp-python. Appears nowhere
in the substrate or gate — it phrases gate-cleared content and parses
utterances; it is never a source of facts.

Pinned artifact (notebook entries 5, 9):
  ggml-org/SmolLM3-3B-GGUF / SmolLM3-Q4_K_M.gguf
  sha256 8334b850b7bd46238c16b0c550df2138f0889bf433809008cc17a8b05761863e
Runtime: llama-cpp-python 0.3.34 CPU wheel. CPU inference is the accepted
path for E3 (no working ROCm userspace in this WSL2 env at build time —
entry 5 addendum); n_gpu_layers stays 0 for reproducibility either way.
"""

import os
import re

MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "models", "SmolLM3-Q4_K_M.gguf")
MODEL_SHA256 = "8334b850b7bd46238c16b0c550df2138f0889bf433809008cc17a8b05761863e"

_llm = None
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def get_llm(n_ctx=4096, n_threads=None, seed=42):
    """GPU (hipBLAS, gfx1100) when available, with the mandatory --cpu
    fallback: RG_CPU=1 forces CPU, and a failed GPU load falls back
    automatically. Backend used is printed once — log it with any measured
    numbers (CPU/GPU token streams differ under sampling)."""
    global _llm
    if _llm is None:
        from llama_cpp import Llama
        kw = dict(n_ctx=n_ctx, n_threads=n_threads or os.cpu_count(),
                  seed=seed, verbose=False)
        import llama_cpp
        gpu_capable = bool(llama_cpp.llama_supports_gpu_offload())
        if os.environ.get("RG_CPU") == "1" or not gpu_capable:
            _llm = Llama(MODEL_PATH, n_gpu_layers=0, **kw)
            why = "forced via RG_CPU=1" if gpu_capable else "build has no GPU offload"
            print(f"[mouth] backend: CPU ({why})")
        else:
            try:
                _llm = Llama(MODEL_PATH, n_gpu_layers=-1, **kw)
                print("[mouth] backend: GPU (n_gpu_layers=-1)")
            except Exception as e:
                print(f"[mouth] GPU load failed ({e!r}); falling back to CPU")
                _llm = Llama(MODEL_PATH, n_gpu_layers=0, **kw)
    return _llm


def _strip_think(text):
    """SmolLM3 sometimes emits reasoning-block remnants even under /no_think;
    strip complete blocks and any dangling tag prefix."""
    text = _THINK_RE.sub("", text)
    if "</think>" in text:
        text = text.split("</think>")[-1]
    return text.strip()


def generate(system, user, max_tokens=64, temperature=0.0, seed=None):
    """One chat completion. temperature=0 is deterministic; sampled calls
    must pass an explicit seed (all randomness seeded — hard rule)."""
    llm = get_llm()
    if seed is not None:
        llm.set_seed(seed)
    out = llm.create_chat_completion(
        messages=[{"role": "system", "content": "/no_think " + system},
                  {"role": "user", "content": user}],
        max_tokens=max_tokens, temperature=temperature,
    )
    return _strip_think(out["choices"][0]["message"]["content"])


def verify_hash():
    import hashlib
    h = hashlib.sha256()
    with open(MODEL_PATH, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest() == MODEL_SHA256
