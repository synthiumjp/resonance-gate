"""numpy ports of the small recurrent nets: the MWT character classifier and the
lemmatizer's attention seq2seq (greedy decoding, copy, edit classifier).

Ported from stanza.models.mwt.character_classifier,
stanza.models.common.seq2seq_{model,modules} and stanza.models.lemma.trainer
(Stanza 1.14.0, Apache-2.0).  float32 throughout.
"""
import numpy as np

from .vocab import BaseVocab

PAD_ID, UNK_ID, SOS_ID, EOS_ID = 0, 1, 2, 3
SOS, EOS, UNK = '<SOS>', '<EOS>', '<UNK>'
INFINITY_NUMBER = 1e12
CACHE_MAX = 200000          # the lemma / mwt memo tables are pure functions; bound their size


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def lstm_layer(x, w_ih, w_hh, b_ih, b_hh, reverse=False, h0=None, c0=None):
    """x [L, D] -> (out [L, H], h_last, c_last). torch gate order i, f, g, o."""
    L = x.shape[0]
    H = w_hh.shape[1]
    gx = x @ w_ih.T + (b_ih + b_hh)
    h = np.zeros(H, np.float32) if h0 is None else h0
    c = np.zeros(H, np.float32) if c0 is None else c0
    out = np.empty((L, H), np.float32)
    rng = range(L - 1, -1, -1) if reverse else range(L)
    wt = w_hh.T
    for t in rng:
        g = gx[t] + h @ wt
        i = _sigmoid(g[:H]); f = _sigmoid(g[H:2 * H]); gg = np.tanh(g[2 * H:3 * H]); o = _sigmoid(g[3 * H:])
        c = f * c + i * gg
        h = o * np.tanh(c)
        out[t] = h
    return out, h, c


def bilstm(x, w, prefix, nlayers):
    """Stacked bidirectional torch nn.LSTM weights under `prefix` (no dropout at eval).
    returns out [L, 2H], and final (h, c) of the last layer's fwd and bwd directions."""
    inp = x
    for l in range(nlayers):
        fo, fh, fc = lstm_layer(inp, w[f'{prefix}.weight_ih_l{l}'], w[f'{prefix}.weight_hh_l{l}'],
                                w[f'{prefix}.bias_ih_l{l}'], w[f'{prefix}.bias_hh_l{l}'])
        bo, bh, bc = lstm_layer(inp, w[f'{prefix}.weight_ih_l{l}_reverse'], w[f'{prefix}.weight_hh_l{l}_reverse'],
                                w[f'{prefix}.bias_ih_l{l}_reverse'], w[f'{prefix}.bias_hh_l{l}_reverse'], reverse=True)
        inp = np.concatenate([fo, bo], axis=1)
    return inp, (fh, bh), (fc, bc)


class MWTExpander:
    """MWT processor: dictionary first, CharacterClassifier for the rest."""

    def __init__(self, cfg, weights):
        self.cfg = cfg["config"]
        self.vocab = BaseVocab(cfg["vocab"])
        self.dict = cfg["dict"]
        self.w = weights
        self.nlayers = self.cfg["num_layers"]
        self.vocab_size = self.cfg["vocab_size"]
        assert self.cfg["force_exact_pieces"] and not self.cfg["dict_only"]
        self.emb = weights['embedding.weight']
        self._cache = {}

    def dict_expansion(self, word):
        expansion = self.dict.get(word)
        if expansion is not None:
            return expansion
        if word.isupper():
            expansion = self.dict.get(word.lower())
            if expansion is not None:
                return expansion.upper()
        if word[0].isupper() and word[1:].islower():
            expansion = self.dict.get(word.lower())
            if expansion is not None:
                return expansion[0].upper() + expansion[1:]
        return None

    def _classify(self, word):
        ids = [SOS_ID] + [self.vocab.unit2id(c) for c in word] + [EOS_ID]
        ids = [i if i < self.vocab_size else UNK_ID for i in ids]
        x = self.emb[ids]
        enc, _, _ = bilstm(x, self.w, 'encoder', self.nlayers)
        h = np.maximum(enc @ self.w['output_layer.0.weight'].T + self.w['output_layer.0.bias'], 0)
        logits = h @ self.w['output_layer.2.weight'].T + self.w['output_layer.2.bias']
        cut = logits[:, 1] > logits[:, 0]
        pred_seq = []
        for char_idx in range(1, len(ids) - 1):
            if cut[char_idx]:
                pred_seq.append(' ')
            pred_seq.append(word[char_idx - 1])
        return "".join(pred_seq).strip()

    def expand(self, word):
        """One expansion string for an MWT token text (Trainer.predict + ensemble)."""
        r = self._cache.get(word)
        if r is None:
            r = self.dict_expansion(word)
            if r is None:
                r = self._classify(word)
            if len(self._cache) >= CACHE_MAX:
                self._cache.clear()
            self._cache[word] = r
        return r


class Lemmatizer:
    """Lemma processor: dictionary lookup, seq2seq (+edit classifier) for words not in it."""

    def __init__(self, cfg, weights):
        self.cfg = cfg["config"]
        self.char_vocab = BaseVocab(cfg["char"])
        self.pos_vocab = BaseVocab(cfg["pos"])
        self.pos_dict = cfg["pos_dict"]
        self.w = weights
        c = self.cfg
        assert c["beam_size"] == 1 and c["edit"] and c["copy"] and c["pos"] and c["attn_type"] == "soft"
        assert c["num_layers"] == 1 and not c["caseless"]
        self.vocab_size = c["vocab_size"]
        self.max_dec_len = c["max_dec_len"]
        self.emb = weights['embedding.weight']
        self.pos_emb = weights['pos_embedding.weight']
        self.caseless = c["caseless"]
        self._cache = {}

    # -- dictionary
    def lookup(self, w, pos):
        pos_entries = self.pos_dict.get(pos)
        if pos_entries is not None:
            lemma = pos_entries.get(w)
            if lemma is not None:
                return lemma
        fallback = self.pos_dict.get("*")
        if fallback is not None:
            return fallback.get(w)
        return None

    # -- seq2seq
    def _decode_word(self, word, pos):
        """-> (predicted lemma string, edit id)"""
        w = self.w
        V = self.vocab_size
        # DeltaVocab: characters unseen in training get ids >= V (their numbering is
        # irrelevant to the result; only that they are distinct and >= V)
        extra = {}
        src = [SOS_ID]
        for ch in word:
            i = self.char_vocab._unit2id.get(ch)
            if i is None:
                i = extra.setdefault(ch, V + len(extra))
            src.append(i)
        src.append(EOS_ID)
        src = np.array(src, dtype=np.int64)
        extra_by_id = {v: k for k, v in extra.items()}
        embed_src = np.where(src >= V, UNK_ID, src)
        pos_id = self.pos_vocab.unit2id(pos)
        enc_in = np.concatenate([self.pos_emb[pos_id][None], self.emb[embed_src]], axis=0)   # [1+L, E]
        h_in, (hf, hb), (cf, cb) = bilstm(enc_in, w, 'encoder', 1)
        # torch: hn = cat((hn[-1], hn[-2]), 1); hn[-1] is the backward direction of the
        # last layer, hn[-2] the forward one.
        hn = np.concatenate([hb, hf])
        cn = np.concatenate([cb, cf])
        edit_h = np.maximum(hn @ w['edit_clf.0.weight'].T + w['edit_clf.0.bias'], 0)
        edit_logits = edit_h @ w['edit_clf.2.weight'].T + w['edit_clf.2.bias']
        edit = int(np.argmax(edit_logits))

        w_ih = w['decoder.lstm_cell.weight_ih']; w_hh = w['decoder.lstm_cell.weight_hh']
        b = w['decoder.lstm_cell.bias_ih'] + w['decoder.lstm_cell.bias_hh']
        lin_in = w['decoder.attention_layer.linear_in.weight']
        lin_out = w['decoder.attention_layer.linear_out.weight']
        d2v_w, d2v_b = w['dec2vocab.weight'], w['dec2vocab.bias']
        cg_w, cg_b = w['copy_gate.weight'], w['copy_gate.bias']
        H = hn.shape[0]
        cur = self.emb[SOS_ID]
        out_ids = []
        h, c = hn, cn
        src_max = int(src.max())
        for _ in range(self.max_dec_len):
            g = w_ih @ cur + w_hh @ h + b
            i_ = _sigmoid(g[:H]); f_ = _sigmoid(g[H:2 * H]); gg = np.tanh(g[2 * H:3 * H]); o_ = _sigmoid(g[3 * H:])
            c = f_ * c + i_ * gg
            h = o_ * np.tanh(c)
            # soft dot attention over h_in (no padding: batch of one)
            target = lin_in @ h
            attn = h_in @ target
            mx_a = attn.max()
            log_attn = (attn - mx_a) - np.log(np.exp(attn - mx_a).sum())
            attn_w = np.exp(log_attn)
            weighted = attn_w @ h_in
            h_tilde = np.tanh(lin_out @ np.concatenate([weighted, h]))
            logits = d2v_w @ h_tilde + d2v_b
            lm = logits.max()
            log_probs = (logits - lm) - np.log(np.exp(logits - lm).sum())
            # copy mechanism
            copy_logit = (cg_w @ h_tilde + cg_b)[0]
            la = log_attn[1:]                      # can't copy the UPOS
            lam = la.max()
            la = (la - lam) - np.log(np.exp(la - lam).sum())
            log_copy = (-np.logaddexp(0.0, -copy_logit)) + la     # logsigmoid(copy_logit) + log_attn
            mx = log_copy.max()
            copy_prob = np.exp(log_copy - mx)
            shape = V
            if src_max >= shape:
                shape = src_max + 1
            copied = np.zeros(shape, np.float32)
            np.add.at(copied, src, copy_prob)
            zero_mask = copied == 0
            log_copied = np.log(np.where(zero_mask, np.float32(1e-12), copied)) + mx
            log_copied = np.where(zero_mask, np.float32(-1e12), log_copied)
            log_nocopy = -np.log(1 + np.exp(copy_logit))
            if V < shape:
                new_lp = np.zeros(shape, np.float32)
                new_lp[:V] = log_probs
                new_lp[V:] = new_lp[UNK_ID]
                log_probs = new_lp
            log_probs = log_probs + log_nocopy
            m2 = np.maximum(log_copied, log_probs)
            log_probs = m2 + np.log(np.exp(log_copied - m2) + np.exp(log_probs - m2))
            pred = int(np.argmax(log_probs))
            if pred == EOS_ID:
                break
            out_ids.append(pred)
            cur = self.emb[UNK_ID if pred >= V else pred]
        pieces = [self.char_vocab._id2unit[i] if i < V else extra_by_id[i] for i in out_ids]
        return "".join(pieces), edit

    def predict(self, word, upos):
        """Full lemma for (word, upos) as the lemma processor returns it (before the '_' fix)."""
        key = (word, upos)
        r = self._cache.get(key)
        if r is not None:
            return r
        lem = self.lookup(word, upos)
        if lem is None:
            pred, edit = self._decode_word(word, upos)
            if edit == 1:
                lem = word
            elif edit == 2:
                lem = word.lower()
            else:
                lem = pred
            if len(lem) == 0 or UNK in lem:
                lem = word
        if len(self._cache) >= CACHE_MAX:
            self._cache.clear()
        self._cache[key] = lem
        return lem
