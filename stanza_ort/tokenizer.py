"""Neural tokenizer: feature extraction, windowed prediction and decoding.

The data preparation and decoding logic is ported from
stanza.models.tokenization.{data,utils} and stanza.pipeline.tokenize_processor
(Stanza 1.14.0, Apache-2.0).  The network itself is the tok.onnx graph
(batch size 1; one call per paragraph, over exactly the characters Stanza's
packed LSTM would see).
"""
import re
import numpy as np

from .doc import Document, ID, TEXT, MISC, START_CHAR, END_CHAR
from .vocab import BaseVocab
from ._tokregex import (NEWLINE_WHITESPACE_RE, NUMERIC_RE, WHITESPACE_RE, SPACE_SPLIT_RE, MASK_RE,
                        STRUCTURAL_FEATURES)

SPACE_RE = re.compile(r'\s')
PAD = '<PAD>'
MAX_SEQLEN_FLOOR = 1000          # output_predictions: max_seqlen = max(1000, max_seqlen)
TOKEN_TOO_LONG_REPLACEMENT = "<UNK>"

PER_CHAR_FEAT_FUNCS = {
    'space_before': lambda x: 1 if x.startswith(' ') else 0,
    'capitalized': lambda x: 1 if x[0].isupper() else 0,
    'numeric': lambda x: 1 if (NUMERIC_RE.match(x) is not None) else 0,
}
POSITION_FEAT_FUNCS = frozenset({'end_of_para', 'start_of_para'})


def _filter_consecutive_whitespaces(chars):
    out = []
    for i, ch in enumerate(chars):
        if i > 0 and ch == ' ' and chars[i - 1] == ' ':
            continue
        out.append(ch)
    return out


class Tokenizer:
    def __init__(self, cfg, session):
        self.cfg = cfg
        self.sess = session
        self.vocab = BaseVocab(cfg["vocab"])
        self.lang_replaces_spaces = cfg["lang_replaces_spaces"]
        self.skip_newline = cfg["skip_newline"]
        self.max_seqlen_cfg = cfg["max_seqlen"]
        self.batch_size = cfg["batch_size"]
        self.feat_funcs = cfg["feat_funcs"]
        self.padid = self.vocab.unit2id(PAD)
        self.feat_dim = cfg["feat_dim"]
        funcs = []
        for f in self.feat_funcs:
            if f in POSITION_FEAT_FUNCS or f in STRUCTURAL_FEATURES:
                continue
            funcs.append(PER_CHAR_FEAT_FUNCS[f])
        self._funcs = funcs
        self._use_end = 'end_of_para' in self.feat_funcs
        self._use_start = 'start_of_para' in self.feat_funcs
        self._structural = [n for n in STRUCTURAL_FEATURES if n in self.feat_funcs]

    # ------------------------------------------------------------ data prep
    def paragraphs(self, text):
        chunks = NEWLINE_WHITESPACE_RE.split(text)
        chunks = [pt.rstrip() for pt in chunks]
        chunks = [pt for pt in chunks if pt]
        data = [[WHITESPACE_RE.sub(' ', ch) for ch in pt if not (self.skip_newline and ch == '\n')]
                for pt in chunks]
        return [_filter_consecutive_whitespaces(x) for x in data]

    def featurize(self, para):
        """para: list of single characters -> (unit ids [n], feats [n, F] float32)"""
        n = len(para)
        feats = np.zeros((n, self.feat_dim), np.float32)
        ids = np.fromiter((self.vocab.unit2id(c) for c in para), dtype=np.int64, count=n)
        masks = {}
        if self._structural:
            raw = ''.join(para)
            for name in self._structural:
                m = np.zeros(n, np.float32)
                for mt in STRUCTURAL_FEATURES[name].finditer(raw):
                    m[mt.start():mt.end()] = 1
                masks[name] = m
        nf = len(self._funcs)
        for i, c in enumerate(para):
            for k, f in enumerate(self._funcs):
                feats[i, k] = f(c)
        col = nf
        if self._use_end:
            feats[n - 1, col] = 1
            col += 1
        if self._use_start:
            feats[0, col] = 1
            col += 1
        for name in self._structural:
            feats[:, col] = masks[name]
            col += 1
        assert col == self.feat_dim, (col, self.feat_dim)
        return ids, feats

    # ------------------------------------------------------------ network
    def _run_row(self, units, feats):
        """units [L] int64, feats [L,F] -> argmax over 5 classes [L]"""
        out = self.sess.run(None, {'x': units[None], 'feats': feats[None]})[0][0]
        return np.argmax(out, axis=1)

    def _predict_batch(self, units, feats, raw):
        """units [B,P], feats [B,P,F], raw: list of lists -> int array [B, min(P, longest)]
        Each row is run over len(raw[row]) positions, as Stanza's packed LSTM does."""
        B = len(raw)
        width = max(len(r) for r in raw)
        pred = np.zeros((B, width), dtype=np.int64)
        for j in range(B):
            L = len(raw[j])
            pred[j, :L] = self._run_row(units[j, :L], feats[j, :L])
        return pred

    @staticmethod
    def _find_spans(raw):
        pads = [idx for idx, ch in enumerate(raw) if ch == '<PAD>']
        if len(pads) == 0:
            return [(0, len(raw))]
        prev = 0
        spans = []
        for pad in pads:
            if pad != prev:
                spans.append((prev, pad))
            prev = pad + 1
        if prev < len(raw):
            spans.append((prev, len(raw)))
        return spans

    def _update_pred_regex(self, raw, pred):
        for span_begin, span_end in self._find_spans(raw):
            text = "".join(raw[span_begin:span_end])
            for match in MASK_RE.finditer(text):
                match_begin, match_end = match.span()
                for ch in range(match_begin + span_begin, match_end + span_begin - 1):
                    pred[ch] = 0
                if pred[match_end + span_begin - 1] == 0:
                    pred[match_end + span_begin - 1] = 1
        return pred

    def _advance_old_batch(self, eval_offsets, old_batch):
        ounits, ofeatures, oraw = old_batch
        padid = self.padid
        feat_size = ofeatures.shape[-1]
        lens = (ounits != padid).sum(1).tolist()
        pad_len = max(l - i for i, l in zip(eval_offsets, lens))
        n = len(ounits)
        units = np.full((n, pad_len), padid, dtype=np.int64)
        features = np.zeros((n, pad_len, feat_size), dtype=np.float32)
        raw_units = []
        for i in range(n):
            eval_offsets[i] = min(eval_offsets[i], lens[i])
            units[i, :(lens[i] - eval_offsets[i])] = ounits[i, eval_offsets[i]:lens[i]]
            features[i, :(lens[i] - eval_offsets[i])] = ofeatures[i, eval_offsets[i]:lens[i]]
            raw_units.append(oraw[i][eval_offsets[i]:lens[i]] + [PAD] * (pad_len - lens[i] + eval_offsets[i]))
        return units, features, raw_units

    def predict(self, paras):
        """paras: list of paragraphs (lists of chars).  Returns (all_preds, all_raw) in input order."""
        max_seqlen = max(MAX_SEQLEN_FLOOR, self.max_seqlen_cfg)   # output_predictions
        prepared = [self.featurize(p) if p else None for p in paras]
        order = _stanza_sort_order([len(p) for p in paras])
        bs = self.batch_size
        all_preds = [None] * len(paras)
        all_raw = [None] * len(paras)
        for b0 in range(0, len(order), bs):
            idxs = order[b0:b0 + bs]
            n = len(idxs)
            # collate: every raw row gets exactly one trailing <PAD>
            pad_len = max(len(paras[i]) for i in idxs) + 1
            F = self.feat_dim
            units = np.full((n, pad_len), self.padid, dtype=np.int64)
            feats = np.zeros((n, pad_len, F), dtype=np.float32)
            raw = []
            for r, i in enumerate(idxs):
                u, f = prepared[i]
                units[r, :len(u)] = u
                feats[r, :len(u)] = f
                raw.append(list(paras[i]) + [PAD])
            N = len(raw[0])
            if N <= max_seqlen:
                pred = self._predict_batch(units, feats, raw)
            else:
                idx = [0] * n
                adv = [0] * n
                para_lengths = [x.index(PAD) for x in raw]
                preds = [[] for _ in range(n)]
                batch = (units, feats, raw)
                while True:
                    ens = [min(N_ - idx1, max_seqlen) for idx1, N_ in zip(idx, para_lengths)]
                    en = max(ens)
                    u1, f1, r1 = batch[0][:, :en], batch[1][:, :en], [x[:en] for x in batch[2]]
                    pred1 = self._predict_batch(u1, f1, r1)
                    for j in range(n):
                        sentbreaks = np.where((pred1[j] == 2) + (pred1[j] == 4))[0]
                        if len(sentbreaks) <= 0 or idx[j] >= para_lengths[j] - max_seqlen:
                            advance = ens[j]
                        else:
                            advance = np.max(sentbreaks) + 1
                        preds[j] += [pred1[j, :advance]]
                        idx[j] += advance
                        adv[j] = advance
                    if all([idx1 >= N_ for idx1, N_ in zip(idx, para_lengths)]):
                        break
                    batch = self._advance_old_batch(adv, batch)
                pred = [np.concatenate(p, 0) for p in preds]
            for r, i in enumerate(idxs):
                rawr = raw[r]
                par_len = rawr.index(PAD)
                rawr = rawr[:par_len]
                pr = pred[r]
                if pr[par_len - 1] < 2:
                    pr[par_len - 1] = 2
                elif pr[par_len - 1] > 2:
                    pr[par_len - 1] = 4
                all_preds[i] = self._update_pred_regex(rawr, pr[:par_len])
                all_raw[i] = rawr
        return all_preds, all_raw

    # ------------------------------------------------------------ decode
    def normalize_token(self, token):
        token = SPACE_RE.sub(' ', token.lstrip())
        if self.lang_replaces_spaces:
            token = token.replace(' ', '')
        return token

    def decode(self, orig_text, all_raw, all_preds, no_ssplit=False):
        doc = []
        text = WHITESPACE_RE.sub(' ', orig_text)
        char_offset = 0
        for raw, pred in zip(all_raw, all_preds):
            current_tok = ''
            current_sent = []
            for t, p in zip(raw, pred):
                if t == PAD:
                    break
                current_tok += t
                if p >= 1:
                    tok = self.normalize_token(current_tok)
                    assert '\t' not in tok, tok
                    if len(tok) <= 0:
                        current_tok = ''
                        continue
                    st = -1
                    for part in SPACE_SPLIT_RE.split(current_tok):
                        if len(part) == 0:
                            continue
                        if self.skip_newline:
                            part_pattern = re.compile(r'\s*'.join(re.escape(c) for c in part))
                            match = part_pattern.search(text, char_offset)
                            st0 = match.start(0) - char_offset
                            partlen = match.end(0) - match.start(0)
                            lstripped = match.group(0).lstrip()
                        else:
                            try:
                                st0 = text.index(part, char_offset) - char_offset
                            except ValueError as e:
                                sub = text[max(0, char_offset - 20):min(len(text), char_offset + 20)]
                                raise ValueError("Could not find |%s| starting from char_offset %d.  Surrounding text: |%s|" % (part, char_offset, sub)) from e
                            partlen = len(part)
                            lstripped = part.lstrip()
                        if st < 0:
                            st = char_offset + st0 + (partlen - len(lstripped))
                        char_offset += st0 + partlen
                    current_sent.append((tok, p, (st, char_offset)))
                    current_tok = ''
                    if (p == 2 or p == 4) and not no_ssplit:
                        doc.append(self._process_sentence(current_sent))
                        current_sent = []
            if len(current_tok) > 0:
                raise ValueError("Finished processing tokens, but there is still text left!")
            if len(current_sent):
                doc.append(self._process_sentence(current_sent))
        return doc

    @staticmethod
    def _process_sentence(sentence):
        sent = []
        i = 0
        for tok, p, position_info in sentence:
            if len(tok) <= 0:
                continue
            sent.append({ID: (i + 1,), TEXT: tok})
            if position_info is not None:
                sent[-1][START_CHAR] = position_info[0]
                sent[-1][END_CHAR] = position_info[1]
            if p == 3 or p == 4:
                sent[-1][MISC] = 'MWT=Yes'
            i += 1
        return sent

    # ------------------------------------------------------------ processor
    def process(self, text):
        """str -> Document (tokens, sentence splits, MWT flags; words not yet expanded)"""
        paras = self.paragraphs(text)
        preds, raws = self.predict(paras)
        sents = self.decode(text, raws, preds)
        for sentence in sents:
            for token in sentence:
                if len(token['text']) > self.max_seqlen_cfg:
                    token['text'] = TOKEN_TOO_LONG_REPLACEMENT
        return Document(sents, text)

    def bulk_process(self, docs):
        """Same as TokenizeProcessor.bulk_process: join with blank lines, tokenize once,
        split the sentences back into the documents."""
        combined_text = '\n\n'.join([d.text for d in docs])
        processed_combined = self.process(combined_text)
        charoffset = 0
        sentst = senten = 0
        for thisdoc in docs:
            while senten < len(processed_combined.sentences) and processed_combined.sentences[senten].tokens[-1].end_char - charoffset <= len(thisdoc.text):
                senten += 1
            sentences = processed_combined.sentences[sentst:senten]
            thisdoc.sentences = sentences
            for sent in sentences:
                sent._doc = thisdoc
                for token in sent.tokens:
                    token._start_char -= charoffset
                    token._end_char -= charoffset
                    if token.words:
                        for word in token.words:
                            word._start_char -= charoffset
                            word._end_char -= charoffset
            if len(sentences) > 0:
                last_token = sentences[-1].tokens[-1]
                last_token.spaces_after = thisdoc.text[last_token.end_char:]
                first_token = sentences[0].tokens[0]
                first_token.spaces_before = thisdoc.text[:first_token.start_char]
            thisdoc.num_tokens = sum(len(sent.tokens) for sent in sentences)
            thisdoc.num_words = sum(len(sent.words) for sent in sentences)
            sentst = senten
            charoffset += len(thisdoc.text) + 2
        return docs


def _stanza_sort_order(lengths):
    """Replicates stanza.models.common.utils.sort_with_indices(key=len, reverse=True)."""
    ind = list(range(len(lengths)))
    # sort_with_indices: sorted(zip(range, data), key=lambda t: key(t[1]), reverse=True)
    ind.sort(key=lambda i: lengths[i], reverse=True)
    return ind
