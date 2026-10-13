"""Which Stanza English models convert.py converts and parity.py compares
against (2026-10-13, the parser licence).

    STANZA_PACKAGES=        (unset) Stanza's default "combined" models
    STANZA_PACKAGES=ewt     Stanza's EWT-only models (their POS and depparse use the
                            CoNLL 2017 vectors, CC BY-NC-SA, and the 1billion charlm)
    STANZA_PACKAGES=ewt_nocharlm   the same without the charlm (a parity test of the
                            character-model path)
    STANZA_PACKAGES=ours    tokenizer, mwt and lemma from Stanza's EWT-only models,
                            POS and depparse trained by us on EWT with GloVe (PDDL),
                            no charlm: STANZA_POS_MODEL, STANZA_DEP_MODEL, STANZA_PRETRAIN
"""
import os

PACKAGES = {
    "ewt": {"tokenize": "ewt", "mwt": "ewt", "pos": "ewt_charlm", "lemma": "ewt_nocharlm", "depparse": "ewt_charlm"},
    "ewt_nocharlm": {"tokenize": "ewt", "mwt": "ewt", "pos": "ewt_nocharlm", "lemma": "ewt_nocharlm",
                     "depparse": "ewt_nocharlm"},
    "ours": {"tokenize": "ewt", "mwt": "ewt", "pos": "ewt_nocharlm", "lemma": "ewt_nocharlm",
             "depparse": "ewt_nocharlm"},
}


def pipeline_kwargs():
    """-> keyword arguments for stanza.Pipeline("en", ...)."""
    name = os.environ.get("STANZA_PACKAGES", "")
    if not name:
        return {"processors": "tokenize,pos,lemma,depparse"}
    kw = {"processors": dict(PACKAGES[name]), "package": None}
    if name == "ours":
        kw.update(pos_model_path=os.environ["STANZA_POS_MODEL"],
                  depparse_model_path=os.environ["STANZA_DEP_MODEL"],
                  pos_pretrain_path=os.environ["STANZA_PRETRAIN"],
                  depparse_pretrain_path=os.environ["STANZA_PRETRAIN"])
    return kw
