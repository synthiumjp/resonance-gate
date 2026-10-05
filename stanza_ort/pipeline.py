"""stanza_ort.Pipeline: Stanza 1.14.0 English tokenize,mwt,pos,lemma,depparse
without torch (numpy + onnxruntime only)."""
import json
import os

import numpy as np
import onnxruntime as ort

from .doc import Document
from .tokenizer import Tokenizer
from .seq2seq import MWTExpander, Lemmatizer
from .tagger import CharLM, Pretrain, Tagger, Parser
from .charlm import NumpyCharLSTM


def _session(path, threads):
    so = ort.SessionOptions()
    so.intra_op_num_threads = threads
    so.inter_op_num_threads = 1
    so.log_severity_level = 3
    # dynamic shapes: memory-pattern planning and the CPU arena only bloat RSS
    if os.environ.get("STANZA_ORT_ARENA", "0") == "0":
        so.enable_mem_pattern = False
        so.enable_cpu_mem_arena = False
    return ort.InferenceSession(path, so, providers=['CPUExecutionProvider'])


class Pipeline:
    """Pipeline(models_dir): `pipe(text)` -> Document, `pipe.bulk_process(texts)` -> [Document]."""

    def __init__(self, models_dir, threads=None, resolve_head_constraints=True):
        if threads is None:
            threads = max(1, min(8, os.cpu_count() or 1))
        d = os.fspath(models_dir)
        if not os.path.exists(os.path.join(d, "config.json")):
            raise FileNotFoundError(
                "stanza_ort models not found in %r (no config.json). They are written once by "
                "convert.py, or installed by the product's setup step." % d)
        with open(os.path.join(d, "config.json"), encoding="utf-8") as f:
            cfg = json.load(f)
        self.cfg = cfg
        S = lambda n: _session(os.path.join(d, n + ".onnx"), threads)
        self.tokenizer = Tokenizer(cfg["tokenize"], S("tok"))
        cl = cfg["charlm"]
        mr = int(os.environ.get("STANZA_ORT_NUMPY_CHARLM_MIN_ROWS", "16"))
        npl = lambda n: (NumpyCharLSTM(os.path.join(d, n + ".npz")) if mr > 0 and os.path.exists(os.path.join(d, n + ".npz")) else None)
        charlms = (CharLM(S("charlm_fwd"), cl["fwd"], True, cl["start"], cl["end"], npl("charlm_fwd"), mr),
                   CharLM(S("charlm_bwd"), cl["bwd"], False, cl["start"], cl["end"], npl("charlm_bwd"), mr))
        pre = Pretrain(cfg["pretrain"], os.path.join(d, "pretrain_emb.npy"))
        with np.load(os.path.join(d, "mwt.npz")) as z:
            mwt_w = {k: z[k] for k in z.files}
        with np.load(os.path.join(d, "lemma.npz")) as z:
            lem_w = {k: z[k] for k in z.files}
        self.mwt = MWTExpander(cfg["mwt"], mwt_w)
        self.lemmatizer = Lemmatizer(cfg["lemma"], lem_w)
        self.tagger = Tagger(cfg["pos"], S("pos"), charlms, pre)
        self.parser = Parser(cfg["dep"], cfg["dep_num_relations"], S("dep"), charlms, pre,
                             resolve_head_constraints=resolve_head_constraints)

    # ------------------------------------------------------------------ steps
    def _mwt(self, docs):
        for doc in docs:
            toks = doc.get_mwt_expansions(evaluation=True)
            preds = [self.mwt.expand(t) for t in toks]
            doc.set_mwt_expansions(preds, process_manual_expanded=False)
            doc._count_words()

    def _pos(self, docs):
        sents = [s for doc in docs for s in doc.sentences]
        tags = self.tagger.tag_many([[w.text for w in s.words] for s in sents])
        for s, tg in zip(sents, tags):
            for w, (u, x, f) in zip(s.words, tg):
                w.upos, w.xpos, w.feats = u, x, f

    def _lemma(self, docs):
        for doc in docs:
            for sent in doc.sentences:
                for w in sent.words:
                    lem = self.lemmatizer.predict(w.text, w.upos if w.upos is not None else '_')
                    w.lemma = lem if len(lem) > 0 else '_'

    def _depparse(self, docs):
        sents = [s for doc in docs for s in doc.sentences]
        res = self.parser.parse_many([([w.text for w in s.words], [w.upos for w in s.words],
                                       [w.xpos for w in s.words], [w.lemma for w in s.words]) for s in sents])
        for sent, rs in zip(sents, res):
            for w, (h, r) in zip(sent.words, rs):
                w.head, w.deprel = h, r
            sent.build_dependencies()

    # ------------------------------------------------------------------ API
    def process(self, doc):
        if isinstance(doc, (list, tuple)):
            return self.bulk_process(doc)
        text = doc.text if isinstance(doc, Document) else doc
        if not isinstance(text, str):
            raise ValueError("input should be a str, a Document or a list of them")
        d = self.tokenizer.process(text)
        docs = [d]
        self._mwt(docs)
        self._pos(docs)
        self._lemma(docs)
        self._depparse(docs)
        return d

    __call__ = process

    def bulk_process(self, texts):
        docs = [t if isinstance(t, Document) else Document([], text=t) for t in texts]
        if not docs:
            return []
        self.tokenizer.bulk_process(docs)
        self._mwt(docs)
        self._pos(docs)
        self._lemma(docs)
        self._depparse(docs)
        return docs
