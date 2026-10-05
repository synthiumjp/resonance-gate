"""Torch-free ColBERT (answerai-colbert-small-v1) on onnxruntime + numpy + tokenizers.
model_dir needs: model.onnx, tokenizer.json, colbert_config.json."""
import json, os
import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer


class ColBERT:
    def __init__(self, model_dir, intra_op_threads=0):
        cfg = json.load(open(os.path.join(model_dir, "colbert_config.json")))
        self.cfg = cfg
        self.tok = Tokenizer.from_file(os.path.join(model_dir, "tokenizer.json"))
        self.tok.no_padding()
        self.pad_id = cfg["pad_id"]
        self.skip = np.array(cfg["skiplist_ids"], dtype=np.int64)
        so = ort.SessionOptions()
        so.intra_op_num_threads = intra_op_threads
        self.sess = ort.InferenceSession(os.path.join(model_dir, "model.onnx"), so,
                                         providers=["CPUExecutionProvider"])

    def _ids(self, texts, max_len, prefix_id):
        # max_len-1 tokens (incl. [CLS]/[SEP]) from the tokenizer, then prefix inserted after [CLS]
        self.tok.enable_truncation(max_length=max_len - 1)
        out = []
        for e in self.tok.encode_batch(texts):
            ids = e.ids
            out.append(ids[:1] + [prefix_id] + ids[1:])
        return out

    def _run(self, seqs, attn_lens=None, pad_to=None):
        L = pad_to or max(len(s) for s in seqs)
        n = len(seqs)
        ids = np.full((n, L), self.pad_id, dtype=np.int64)
        am = np.zeros((n, L), dtype=np.int64)
        for i, s in enumerate(seqs):
            ids[i, :len(s)] = s
            am[i, :(attn_lens[i] if attn_lens else len(s))] = 1
        emb = self.sess.run(None, {"input_ids": ids, "attention_mask": am,
                                   "token_type_ids": np.zeros_like(ids)})[0]
        emb = emb / np.maximum(np.linalg.norm(emb, axis=-1, keepdims=True), 1e-12)
        return emb.astype(np.float32), ids, am

    def encode_queries(self, texts):
        c = self.cfg
        QL = c["query_length"]
        seqs = self._ids(texts, QL, c["query_prefix_id"])
        lens = [len(s) for s in seqs]
        # query expansion: pad with [MASK] to query_length; padding not attended but all rows kept/scored
        al = [QL] * len(seqs) if c["attend_to_expansion_tokens"] else lens
        emb, _, _ = self._run(seqs, attn_lens=al, pad_to=QL)
        return [emb[i] for i in range(len(texts))]

    def encode_docs(self, texts, batch_size=64):
        c = self.cfg
        seqs = self._ids(texts, c["document_length"], c["document_prefix_id"])
        order = np.argsort([len(s) for s in seqs])
        res = [None] * len(texts)
        for b in range(0, len(order), batch_size):
            idx = order[b:b + batch_size]
            emb, ids, am = self._run([seqs[i] for i in idx])
            keep = (am == 1) & ~np.isin(ids, self.skip)
            for j, i in enumerate(idx):
                res[i] = emb[j][keep[j]]
        return res


def maxsim(q, d):
    return float((q @ d.T).max(axis=1).sum())
