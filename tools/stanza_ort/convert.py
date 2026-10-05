"""convert.py -- run ONCE, with torch + stanza installed (reference venv).

Reads the Stanza 1.14.0 English models (tokenize, mwt, pos, lemma, depparse,
the two charlms and the pretrain) and writes everything stanza_ort needs into
models/: ONNX graphs, the pretrain embedding (.npy), small numpy weight files
(.npz) for the seq2seq-style nets (mwt, lemma), and config.json holding
vocabularies, configs and dictionaries (builtin types only).
After this the runtime never needs torch or the .pt files.

usage: python convert.py [out_dir]        (STANZA_RESOURCES_DIR must be set)
"""
import os, sys, json
import numpy as np
import torch, torch.nn as nn, torch.nn.functional as F
import stanza
from stanza.models.common.vocab import CompositeVocab, BaseVocab
from stanza.models.common import char_model as cm

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "models"))
os.makedirs(OUT, exist_ok=True)
RES = os.environ.get("STANZA_RESOURCES_DIR", os.path.expanduser("~/stanza_resources"))
torch.set_num_threads(4)

nlp = stanza.Pipeline("en", dir=RES, processors="tokenize,pos,lemma,depparse",
                      download_method=None, use_gpu=False, logging_level="WARN")
P = nlp.processors
assert stanza.__version__ == "1.14.0", stanza.__version__
posm = P["pos"]._trainer.model.eval()
depm = P["depparse"]._trainer.model.eval()
tok_tr = P["tokenize"]._trainer
tokm = tok_tr.model.eval()
lem_tr = P["lemma"]._trainer
mwt_tr = P["mwt"]._trainer


# ---------------------------------------------------------------- vocab -> json
def vocab_json(v):
    if isinstance(v, CompositeVocab):
        for k in v._id2unit.keys():
            assert v._unit2id[k] == {w: i for i, w in enumerate(v._id2unit[k])}
        return {"kind": "composite", "sep": v.sep, "keyed": v.keyed,
                "keys": [str(k) for k in v._id2unit.keys()],
                "id2unit": [list(v._id2unit[k]) for k in v._id2unit.keys()]}
    assert v._unit2id == {w: i for i, w in enumerate(v._id2unit)}, "vocab not reconstructible from id2unit"
    return {"kind": "base", "lower": bool(v.lower), "id2unit": list(v._id2unit)}

# ---------------------------------------------------------------- ONNX export
OPSET = 17

def hlstm(hl, x, h0, c0):
    for l in range(hl.num_layers):
        h, _ = hl.lstm[l].lstm(x, (h0[2*l:2*l+2].expand(2, x.shape[0], -1).contiguous(),
                                   c0[2*l:2*l+2].expand(2, x.shape[0], -1).contiguous()))
        x = h + torch.sigmoid(hl.gate[l](x)) * torch.tanh(hl.highway[l](x))
    return x

def bil(sc, a, b):
    a = torch.cat([a, torch.ones_like(a[..., :1])], -1)
    b = torch.cat([b, torch.ones_like(b[..., :1])], -1)
    W = sc.W_bilin
    return torch.einsum('bti,oij,btj->bto', a, W.weight, b) + W.bias

class CharLM(nn.Module):
    def __init__(s, m): super().__init__(); s.m = m
    def forward(s, chars):
        e = s.m.char_emb(chars)
        h0 = s.m.charlstm_h_init.expand(1, chars.shape[0], -1).contiguous()
        c0 = s.m.charlstm_c_init.expand(1, chars.shape[0], -1).contiguous()
        o, _ = s.m.charlstm.lstm(e, (h0, c0))
        return o

class PosCore(nn.Module):
    def __init__(s, m): super().__init__(); s.m = m
    def forward(s, word, pre, fc, bc):   # 'lens' is wired into the LSTM nodes by add_sequence_lens()
        m = s.m
        x = torch.cat([m.word_emb(word), m.trans_pretrained(pre), fc, bc], 2)
        h = hlstm(m.taggerlstm, x, m.taggerlstm_h_init, m.taggerlstm_c_init)
        uh = F.relu(m.upos_hid(h)); up = m.upos_clf(uh)
        ua = up.argmax(2)
        xh = F.relu(m.xpos_hid(h)); fh = F.relu(m.ufeats_hid(h))
        ue = m.upos_emb(ua)
        xp = bil(m.xpos_clf, xh, ue).argmax(2)
        fs = torch.stack([bil(c, fh, ue).argmax(2) for c in m.ufeats_clf], 2)
        return ua, xp, fs

class DepCore(nn.Module):
    def __init__(s, m): super().__init__(); s.m = m
    def forward(s, word, lemma, upos, xpos, pre, fc, bc):
        m = s.m
        pe = m.upos_emb(upos) + m.xpos_emb(xpos)
        x = torch.cat([m.trans_pretrained(pre), m.word_emb(word), m.lemma_emb(lemma), pe, pe, fc, bc], 2)
        h = hlstm(m.parserlstm, x, m.parserlstm_h_init, m.parserlstm_c_init)
        un = m.unlabeled(h, h).squeeze(3); dr = m.deprel(h, h)
        T = word.shape[1]
        ar = torch.arange(T)
        ho = (ar.view(1, 1, -1) - ar.view(1, -1, 1))
        lin = m.linearization(h, h).squeeze(3)
        un = un + F.logsigmoid(lin * torch.sign(ho).float())
        ds = m.distance(h, h).squeeze(3)
        dp = 1 + F.softplus(ds); dt = torch.abs(ho)
        un = un + (-torch.log((dt.float() - dp) ** 2 / 2 + 1))
        diag = (ar.view(1, -1, 1) == ar.view(1, 1, -1))
        un = un.masked_fill(diag, -float('inf'))
        return un, dr          # raw scores; log_softmax over the real columns is done in numpy

class TokCore(nn.Module):
    def __init__(s, m): super().__init__(); s.m = m
    def forward(s, x, feats):
        m = s.m
        emb = torch.cat([m.embeddings(x), feats], 2)
        inp, _ = m.rnn(emb)
        tok0 = m.tok_clf(inp); sent0 = m.sent_clf(inp); mwt0 = m.mwt_clf(inp)
        inp2 = inp * (1 - torch.sigmoid(-tok0 * m.args['hier_invtemp']))
        inp2, _ = m.rnn2(inp2)
        tok0 = tok0 + m.tok_clf2(inp2); sent0 = sent0 + m.sent_clf2(inp2); mwt0 = mwt0 + m.mwt_clf2(inp2)
        nontok = F.logsigmoid(-tok0); tok = F.logsigmoid(tok0)
        nonsent = F.logsigmoid(-sent0); sent = F.logsigmoid(sent0)
        nonmwt = F.logsigmoid(-mwt0); mwt = F.logsigmoid(mwt0)
        return torch.cat([nontok, tok + nonsent + nonmwt, tok + sent + nonmwt, tok + nonsent + mwt, tok + sent + mwt], 2)

import onnx
from onnx import helper, TensorProto

def add_sequence_lens(path):
    """Give every bidirectional LSTM node a sequence_lens input (graph input 'lens', int32 [B]) so
    that padded batches give each row exactly what Stanza's packed sequences give it."""
    m = onnx.load(path)
    n = 0
    for nd in m.graph.node:
        if nd.op_type == "LSTM":
            assert nd.input[4] == "", list(nd.input)
            nd.input[4] = "lens"
            n += 1
    m.graph.input.append(helper.make_tensor_value_info("lens", TensorProto.INT32, ["B"]))
    onnx.checker.check_model(m)
    onnx.save(m, path)
    return n

def export(mod, args, names, outn, dyn, name, lens=False):
    path = os.path.join(OUT, name + ".onnx")
    torch.onnx.export(mod, args, path, input_names=names, output_names=outn,
                      dynamic_axes=dyn, opset_version=OPSET, dynamo=False)
    if lens:
        print("  LSTM nodes given sequence_lens:", add_sequence_lens(path))
    print("exported", path, os.path.getsize(path) // 2**20, "MB", flush=True)

assert not isinstance(posm.vocab['xpos'], CompositeVocab) and not isinstance(depm.vocab['xpos'], CompositeVocab)
assert tokm.args['conv_res'] is None and tokm.charmodel is None and tokm.args['use_mwt'] and tokm.args['hierarchical']
assert not tok_tr.args.get('use_dictionary') and tok_tr.dictionary is None
assert depm.args.get('linearization') and depm.args.get('distance') and not depm.args.get('use_arc_embedding')
assert not lem_tr.has_contextual_lemmatizers()
assert mwt_tr.args.get('force_exact_pieces') and not mwt_tr.args['dict_only']
assert lem_tr.args['beam_size'] == 1 and lem_tr.args['ensemble_dict'] and not lem_tr.args['dict_only']
assert lem_tr.args['edit'] and lem_tr.args['copy'] and lem_tr.args['pos'] and lem_tr.args['attn_type'] == 'soft'

T = 7
fl = posm.charmodel_forward; bl = posm.charmodel_backward
for nm, m in [('charlm_fwd', fl), ('charlm_bwd', bl)]:
    export(CharLM(m).eval(), (torch.randint(0, 50, (2, 30)),), ['chars'], ['out'],
           {'chars': {0: 'B', 1: 'L'}, 'out': {0: 'B', 1: 'L'}}, nm)
D = posm.pretrained_emb.weight.shape[1]
B = 2
export(PosCore(posm).eval(), (torch.randint(0, 50, (B, T)), torch.randn(B, T, D), torch.randn(B, T, 1024), torch.randn(B, T, 1024)),
       ['word', 'pre', 'fc', 'bc'], ['upos', 'xpos', 'feats'],
       {**{k: {0: 'B', 1: 'T'} for k in ['word', 'pre', 'fc', 'bc', 'upos', 'xpos', 'feats']}}, 'pos', lens=True)
export(DepCore(depm).eval(), (torch.randint(0, 50, (B, T)), torch.randint(0, 50, (B, T)), torch.randint(0, 15, (B, T)),
                              torch.randint(0, 5, (B, T)), torch.randn(B, T, D), torch.randn(B, T, 1024), torch.randn(B, T, 1024)),
       ['word', 'lemma', 'upos', 'xpos', 'pre', 'fc', 'bc'], ['unl', 'dr'],
       {**{k: {0: 'B', 1: 'T'} for k in ['word', 'lemma', 'upos', 'xpos', 'pre', 'fc', 'bc']},
        'unl': {0: 'B', 1: 'T', 2: 'T'}, 'dr': {0: 'B', 1: 'T', 2: 'T'}}, 'dep', lens=True)
export(TokCore(tokm).eval(), (torch.randint(0, 50, (1, 40)), torch.randn(1, 40, tokm.args['feat_dim'])),
       ['x', 'feats'], ['pred'], {'x': {1: 'L'}, 'feats': {1: 'L'}, 'pred': {1: 'L'}}, 'tok')

# charlm weights for the numpy implementation (stanza_ort/charlm.py)
for nm, m in [('charlm_fwd', fl), ('charlm_bwd', bl)]:
    lstm = m.charlstm.lstm
    assert lstm.num_layers == 1 and not lstm.bidirectional and lstm.batch_first
    np.savez(os.path.join(OUT, nm + ".npz"),
             emb=m.char_emb.weight.detach().numpy().astype(np.float32),
             w_ih=lstm.weight_ih_l0.detach().numpy().astype(np.float32),
             w_hh=lstm.weight_hh_l0.detach().numpy().astype(np.float32),
             bias=(lstm.bias_ih_l0 + lstm.bias_hh_l0).detach().numpy().astype(np.float32),
             h0=m.charlstm_h_init.detach().numpy().reshape(-1).astype(np.float32),
             c0=m.charlstm_c_init.detach().numpy().reshape(-1).astype(np.float32))
    print("saved", nm, ".npz")

# pretrain embedding (both pos and depparse use the same file)
pre = P["pos"].pretrain
emb = pre.emb.numpy().astype(np.float32)
assert emb.shape[0] == len(pre.vocab)
assert emb.shape == tuple(posm.pretrained_emb.weight.shape)
np.save(os.path.join(OUT, "pretrain_emb.npy"), emb)
print("pretrain emb", emb.shape)

# ---------------------------------------------------------------- numpy weights
def save_npz(name, sd, skip=()):
    arrs = {k: v.detach().cpu().numpy().astype(np.float32) for k, v in sd.items()
            if v.dtype.is_floating_point and not any(k.startswith(s) for s in skip)}
    np.savez(os.path.join(OUT, name + ".npz"), **arrs)
    print("saved", name, len(arrs), "arrays")

save_npz("mwt", mwt_tr.model.state_dict())
save_npz("lemma", lem_tr.model.state_dict())

# ---------------------------------------------------------------- config.json
def keep(cfg, keys):
    return {k: cfg[k] for k in keys if k in cfg}

tcfg = P["tokenize"].config
cfg = {
    "stanza_version": stanza.__version__,
    "tokenize": {
        "vocab": vocab_json(tok_tr.vocab),
        "lang": tok_tr.vocab.lang,
        "lang_replaces_spaces": bool(tok_tr.vocab.lang_replaces_spaces),
        "feat_funcs": list(tcfg["feat_funcs"]),
        "skip_newline": bool(tcfg.get("skip_newline", False)),
        "max_seqlen": int(tcfg.get("max_seqlen", 1000)),
        "batch_size": int(tok_tr.args["batch_size"]),
        "shorthand": tok_tr.args["shorthand"],
        "feat_dim": int(tokm.args["feat_dim"]),
    },
    "charlm": {
        "start": cm.CHARLM_START, "end": cm.CHARLM_END,
        "fwd": vocab_json(fl.char_vocab()), "bwd": vocab_json(bl.char_vocab()),
    },
    "pretrain": vocab_json(pre.vocab),
    "pos": {k: vocab_json(P["pos"].vocab[k]) for k in ["word", "upos", "xpos", "feats"]},
    "dep": {k: vocab_json(P["depparse"].vocab[k]) for k in ["word", "lemma", "upos", "xpos", "deprel"]},
    "dep_num_relations": int(depm.num_relations),
    "mwt": {
        "config": keep(P["mwt"].config, ["hidden_dim", "emb_dim", "num_layers", "vocab_size", "ensemble_dict", "dict_only", "force_exact_pieces"]),
        "vocab": vocab_json(mwt_tr.vocab),
        "dict": mwt_tr.expansion_dict,
    },
    "lemma": {
        "config": keep(P["lemma"].config, ["hidden_dim", "emb_dim", "num_layers", "vocab_size", "pos_dim", "pos_vocab_size", "max_dec_len",
                                           "beam_size", "edit", "num_edit", "copy", "pos", "caseless", "ensemble_dict", "attn_type"]),
        "char": vocab_json(lem_tr.vocab['char']),
        "pos": vocab_json(lem_tr.vocab['pos']),
        "pos_dict": lem_tr.pos_dict,
    },
}
with open(os.path.join(OUT, "config.json"), "w", encoding="utf-8") as f:
    json.dump(cfg, f, ensure_ascii=False)
print("config.json", os.path.getsize(os.path.join(OUT, "config.json")) // 1024, "KB")
tot = sum(os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT))
print("models/ total", round(tot / 2**20, 1), "MB")
