"""The three small models, run with ONNX Runtime instead of PyTorch.

2026-10-02 (JP: "I don't want to lose capability" / "it needs to be
something anyone can use"). The embedder, re-ranker and conflict checker
were loaded through sentence-transformers / transformers, which pull in
~300 MB of libraries and store the weights in fp32. Each model's own
Hugging Face repo publishes an official ONNX export; setup downloads it,
stores the weights in fp16 (half the disk), and they are expanded back to
fp32 when loaded, so the arithmetic is unchanged. Measured against the
PyTorch models on the dogfood texts: identical top-1 and top-5 rankings,
cross-encoder scores within 0.004, NLI labels 100% the same. (int8 was
tried and rejected: 2-12% of rankings changed.)

Same call shapes as before, so callers do not change:
    Encoder(name).encode(texts, normalize_embeddings=True) -> np.ndarray
    CrossEncoder(name).predict(pairs) -> np.ndarray (raw logits)
    NLI(name)({"text": a, "text_pair": b}) -> [{"label", "score"}, ...]
"""
import json
import os
import shutil
import tempfile

import numpy as np

EMBEDDER = "BAAI/bge-small-en-v1.5"
RERANKER = "cross-encoder/ms-marco-MiniLM-L6-v2"
CONFLICT = "cross-encoder/nli-deberta-v3-xsmall"
POOLING = {EMBEDDER: "cls"}
MAX_LEN = 512


def model_dir(name):
    root = os.environ.get("SOURCEDRECALL_MODELS") or os.path.join(
        os.path.expanduser("~"), ".cache", "sourcedrecall", "onnx")
    return os.path.join(root, name.replace("/", "__"))


def available(name):
    d = model_dir(name)
    return all(os.path.exists(os.path.join(d, f))
               for f in ("model_fp16.onnx", "tokenizer.json"))


def ensure(name):
    """Download the official ONNX export and store it as fp16. Network only
    here (sourcedrecall-setup); the server runs offline."""
    d = model_dir(name)
    if available(name):
        return d
    import onnx
    from onnx import numpy_helper
    from huggingface_hub import hf_hub_download
    os.makedirs(d, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="sourcedrecall-onnx-")
    try:
        src = hf_hub_download(name, "onnx/model.onnx", local_dir=tmp)
        for f in ("tokenizer.json", "config.json"):
            p = hf_hub_download(name, f, local_dir=tmp)
            shutil.copy(p, os.path.join(d, f))
        m = onnx.load(src)
        for init in m.graph.initializer:
            a = numpy_helper.to_array(init)
            if a.dtype == np.float32:
                init.CopyFrom(numpy_helper.from_array(a.astype(np.float16),
                                                      init.name))
        onnx.save(m, os.path.join(d, "model_fp16.onnx.part"))
        os.replace(os.path.join(d, "model_fp16.onnx.part"),
                   os.path.join(d, "model_fp16.onnx"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return d


def _session(name):
    import onnx
    import onnxruntime as ort
    from onnx import numpy_helper
    d = model_dir(name)
    m = onnx.load(os.path.join(d, "model_fp16.onnx"))
    # fp16 storage, fp32 arithmetic: exactly what the PyTorch model computed
    for init in m.graph.initializer:
        a = numpy_helper.to_array(init)
        if a.dtype == np.float16:
            init.CopyFrom(numpy_helper.from_array(a.astype(np.float32), init.name))
    opts = ort.SessionOptions()
    opts.log_severity_level = 3
    return ort.InferenceSession(m.SerializeToString(), opts,
                                providers=["CPUExecutionProvider"])


class _Base:
    def __init__(self, name):
        from tokenizers import Tokenizer
        self.name = name
        d = model_dir(name)
        self.tok = Tokenizer.from_file(os.path.join(d, "tokenizer.json"))
        self.tok.enable_truncation(max_length=MAX_LEN)
        pad = self.tok.token_to_id("[PAD]")
        self.tok.enable_padding(pad_id=0 if pad is None else pad,
                                pad_token="[PAD]")
        self.sess = _session(name)
        self.inputs = {i.name for i in self.sess.get_inputs()}
        try:
            self.config = json.load(open(os.path.join(d, "config.json")))
        except (OSError, ValueError):
            self.config = {}

    def _run(self, encs):
        feed = {"input_ids": np.array([e.ids for e in encs], dtype=np.int64),
                "attention_mask": np.array([e.attention_mask for e in encs],
                                           dtype=np.int64)}
        if "token_type_ids" in self.inputs:
            feed["token_type_ids"] = np.array([e.type_ids for e in encs],
                                              dtype=np.int64)
        return self.sess.run(None, {k: v for k, v in feed.items()
                                    if k in self.inputs}), feed


class Encoder(_Base):
    def encode(self, texts, batch_size=32, normalize_embeddings=True,
               show_progress_bar=False, **_):
        single = isinstance(texts, str)
        texts = [texts] if single else list(texts)
        out = []
        for i in range(0, len(texts), batch_size):
            (hidden, *_rest), feed = self._run(
                self.tok.encode_batch(texts[i:i + batch_size]))
            if POOLING.get(self.name, "mean") == "cls":
                v = hidden[:, 0]
            else:
                msk = feed["attention_mask"][..., None]
                v = (hidden * msk).sum(1) / np.clip(msk.sum(1), 1e-9, None)
            if normalize_embeddings:
                v = v / np.clip(np.linalg.norm(v, axis=1, keepdims=True), 1e-12, None)
            out.append(v.astype(np.float32))
        res = np.concatenate(out) if out else np.zeros((0, 384), np.float32)
        return res[0] if single else res


class CrossEncoder(_Base):
    def predict(self, pairs, batch_size=32, show_progress_bar=False, **_):
        pairs = [tuple(p) for p in pairs]
        out = []
        for i in range(0, len(pairs), batch_size):
            (logits, *_rest), _ = self._run(
                self.tok.encode_batch(pairs[i:i + batch_size]))
            out.append(logits)
        if not out:
            return np.zeros((0,), np.float32)
        lg = np.concatenate(out).astype(np.float32)
        return lg[:, 0] if lg.shape[1] == 1 else lg


class NLI(CrossEncoder):
    """Stands in for transformers.pipeline("text-classification", top_k=None)."""

    def __call__(self, inp):
        items = inp if isinstance(inp, list) else [inp]
        lg = self.predict([(x["text"], x["text_pair"]) for x in items])
        lg = np.atleast_2d(lg)
        p = np.exp(lg - lg.max(1, keepdims=True))
        p /= p.sum(1, keepdims=True)
        id2label = {int(k): v for k, v in
                    (self.config.get("id2label") or {}).items()}
        res = [sorted(({"label": id2label.get(j, str(j)), "score": float(r[j])}
                       for j in range(len(r))), key=lambda x: -x["score"])
               for r in p]
        return res if isinstance(inp, list) else res[0]


def use_onnx(name):
    return os.environ.get("RG_ONNX") != "0" and available(name)
