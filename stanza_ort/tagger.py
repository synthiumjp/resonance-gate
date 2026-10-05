"""Character LMs, POS tagger and dependency parser on onnxruntime.

Batching, vocab mapping and decoding follow stanza.models.pos.{data,trainer},
stanza.models.depparse.{data,model} and stanza.models.common.char_model
(Stanza 1.14.0, Apache-2.0).  The networks are the ONNX graphs written by
convert.py (batch size 1, dynamic length).
"""
import numpy as np

from .vocab import (BaseVocab, PretrainedWordVocab, CompositeVocab, ROOT_ID, VOCAB_PREFIX_SIZE)
from .chuliu_edmonds import chuliu_edmonds_one_root
from .head_constraints import resolve_head_constraint_violations
import re

QUESTION_RE = re.compile("^[?？︖﹖⁇][?？︖﹖⁇!！︕﹗‼]+$")
EXCLAM_RE = re.compile("^[!！︕﹗‼][?？︖﹖⁇!！︕﹗‼]+$")


def simplify_punct_word(w):
    """stanza.models.common.utils.simplify_punct on one word"""
    w = QUESTION_RE.sub("?", w)
    w = EXCLAM_RE.sub("!", w)
    return w


CHAR_BUDGET = 8192      # padded characters per charlm call
MAX_ROWS = 64
TOKEN_BUDGET = 1024     # padded words per pos / depparse call


def _groups(lengths, budget, max_rows):
    """indices sorted by descending length, cut into groups whose padded size stays within budget"""
    order = sorted(range(len(lengths)), key=lambda i: -lengths[i])
    out, cur = [], []
    for i in order:
        if cur and (len(cur) >= max_rows or (len(cur) + 1) * lengths[cur[0]] > budget):
            out.append(cur)
            cur = []
        cur.append(i)
    if cur:
        out.append(cur)
    return out


def _log_softmax(x, axis):
    m = x.max(axis=axis, keepdims=True)
    z = x - m
    return z - np.log(np.exp(z).sum(axis=axis, keepdims=True))


class CharLM:
    """Forward or backward character LM giving one 1024-d vector per word."""

    def __init__(self, session, vocab_cfg, forward, start, end, numpy_lstm=None, min_rows_numpy=16):
        self.sess = session
        self.numpy_lstm = numpy_lstm
        self.min_rows_numpy = min_rows_numpy
        self.vocab = BaseVocab(vocab_cfg)
        self.forward = forward
        self.start, self.end = start, end
        self.pad_id = self.vocab.unit2id(end)

    def _prepare(self, words):
        if not self.forward:
            words = [x[::-1] for x in reversed(words)]
        chars = [self.start]
        offs = []
        for w in words:
            chars.extend(w)
            chars.append(self.end)
            offs.append(len(chars) - 1)
        if not self.forward:
            offs.reverse()
        return self.vocab.map(chars), offs

    def build_many(self, sentences):
        """sentences: list of list of str -> list of [len(words), D] float32
        (as build_char_representation; the LM is causal, so right padding changes nothing)"""
        prep = [self._prepare(w) for w in sentences]
        res = [None] * len(prep)
        for grp in _groups([len(p[0]) for p in prep], CHAR_BUDGET, MAX_ROWS):
            L = len(prep[grp[0]][0])
            ids = np.full((len(grp), L), self.pad_id, dtype=np.int64)
            for r, i in enumerate(grp):
                ids[r, :len(prep[i][0])] = prep[i][0]
            if self.numpy_lstm is not None and len(grp) >= self.min_rows_numpy:
                out = self.numpy_lstm.run(ids)                # [L, B, H]
                for r, i in enumerate(grp):
                    res[i] = out[prep[i][1], r]
            else:
                out = self.sess.run(None, {'chars': ids})[0]    # [B, L, H]
                for r, i in enumerate(grp):
                    res[i] = out[r][prep[i][1]]
        return res


class Pretrain:
    def __init__(self, vocab_cfg, emb_path):
        self.vocab = PretrainedWordVocab(vocab_cfg)
        self.emb = np.load(emb_path, mmap_mode='r')
        assert self.emb.shape[0] == len(self.vocab)

    def map(self, words):
        return self.vocab.map([w.lower() for w in words])


class Tagger:
    def __init__(self, cfg, sess_pos, charlms, pretrain):
        self.sess = sess_pos
        self.fwd, self.bwd = charlms
        self.pre = pretrain
        self.word = BaseVocab(cfg["word"])
        self.upos = BaseVocab(cfg["upos"])
        self.xpos = BaseVocab(cfg["xpos"])
        self.feats = CompositeVocab(cfg["feats"])

    def tag_many(self, sentences):
        """sentences: list of list of str -> list (per sentence) of list of (upos, xpos, feats)"""
        sentences = [[simplify_punct_word(w) for w in ws] for ws in sentences]
        fcs = self.fwd.build_many(sentences)
        bcs = self.bwd.build_many(sentences)
        res = [None] * len(sentences)
        for grp in _groups([len(s) for s in sentences], TOKEN_BUDGET, MAX_ROWS):
            T = len(sentences[grp[0]])
            B = len(grp)
            wid = np.zeros((B, T), np.int64)
            pre = np.zeros((B, T, self.pre.emb.shape[1]), np.float32)
            fc = np.zeros((B, T, fcs[grp[0]].shape[1]), np.float32)
            bc = np.zeros((B, T, bcs[grp[0]].shape[1]), np.float32)
            lens = np.zeros(B, np.int32)
            for r, i in enumerate(grp):
                n = len(sentences[i])
                wid[r, :n] = self.word.map(sentences[i])
                pre[r, :n] = self.pre.emb[self.pre.map(sentences[i])]
                fc[r, :n] = fcs[i]
                bc[r, :n] = bcs[i]
                lens[r] = n
            u, x, f = self.sess.run(None, {'word': wid, 'pre': pre, 'fc': fc, 'bc': bc, 'lens': lens})
            for r, i in enumerate(grp):
                n = len(sentences[i])
                up = self.upos.unmap(u[r, :n].tolist())
                xp = self.xpos.unmap(x[r, :n].tolist())
                fe = self.feats.unmap(f[r, :n].tolist())
                res[i] = list(zip(up, xp, fe))
        return res


class Parser:
    def __init__(self, cfg, num_relations, sess_dep, charlms, pretrain, resolve_head_constraints=True):
        self.sess = sess_dep
        self.fwd, self.bwd = charlms
        self.pre = pretrain
        self.word = BaseVocab(cfg["word"])
        self.lemma = BaseVocab(cfg["lemma"])
        self.upos = BaseVocab(cfg["upos"])
        self.xpos = BaseVocab(cfg["xpos"])
        self.deprel = BaseVocab(cfg["deprel"])
        self.num_relations = num_relations
        self.resolve = resolve_head_constraints

    def parse_many(self, sentences):
        """sentences: list of (words, upos, xpos, lemmas) -> list of list of (head, deprel)"""
        fix = lambda xs: ['_' if x is None else x for x in xs]
        sents = [([simplify_punct_word(w) for w in ws], fix(up), fix(xp), fix(lm)) for ws, up, xp, lm in sentences]
        ct = [["\n"] + s[0] for s in sents]
        fcs = self.fwd.build_many(ct)
        bcs = self.bwd.build_many(ct)
        res = [None] * len(sents)
        for grp in _groups([len(s[0]) + 1 for s in sents], TOKEN_BUDGET, MAX_ROWS):
            T = len(sents[grp[0]][0]) + 1
            B = len(grp)
            wid = np.zeros((B, T), np.int64); lid = np.zeros((B, T), np.int64)
            uid = np.zeros((B, T), np.int64); xid = np.zeros((B, T), np.int64)
            pre = np.zeros((B, T, self.pre.emb.shape[1]), np.float32)
            fc = np.zeros((B, T, fcs[grp[0]].shape[1]), np.float32)
            bc = np.zeros((B, T, bcs[grp[0]].shape[1]), np.float32)
            lens = np.zeros(B, np.int32)
            for r, i in enumerate(grp):
                ws, up, xp, lm = sents[i]
                n = len(ws) + 1
                wid[r, :n] = [ROOT_ID] + self.word.map(ws)
                lid[r, :n] = [ROOT_ID] + self.lemma.map(lm)
                uid[r, :n] = [ROOT_ID] + self.upos.map(up)
                xid[r, :n] = [ROOT_ID] + self.xpos.map(xp)
                pre[r, :n] = self.pre.emb[[ROOT_ID] + self.pre.map(ws)]
                fc[r, :n] = fcs[i]
                bc[r, :n] = bcs[i]
                lens[r] = n
            unl, dr = self.sess.run(None, {'word': wid, 'lemma': lid, 'upos': uid, 'xpos': xid,
                                           'pre': pre, 'fc': fc, 'bc': bc, 'lens': lens})
            for r, i in enumerate(grp):
                l = len(sents[i][0]) + 1
                scores = _log_softmax(unl[r, :l, :l], 1)
                tree = chuliu_edmonds_one_root(scores)
                if self.resolve:
                    label_log_probs = _log_softmax(dr[r, :l, :l, :], 2)
                    tree, raw_label_ids = resolve_head_constraint_violations(scores, label_log_probs, tree, self.deprel)
                    deprels = self.deprel.unmap([k + VOCAB_PREFIX_SIZE for k in raw_label_ids])
                else:
                    labels = dr[r, :l, :l, :].argmax(2) + VOCAB_PREFIX_SIZE
                    hs = tree[1:]
                    deprels = self.deprel.unmap([labels[j + 1][h] for j, h in enumerate(hs)])
                heads = tree[1:]
                res[i] = [(int(heads[j]), deprels[j]) for j in range(l - 1)]
        return res
