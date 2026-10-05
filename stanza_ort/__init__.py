"""stanza_ort: torch-free runtime for the Stanza 1.14.0 English pipeline
(tokenize, mwt, pos, lemma, depparse).  Needs only numpy and onnxruntime.

    from stanza_ort import Pipeline, Document
    nlp = Pipeline("models")
    doc = nlp("I moved to Lisbon in 2019.")
    docs = nlp.bulk_process([Document([], text=t) for t in texts])   # or plain strings
"""
from .doc import Document, Sentence, Token, Word
from .pipeline import Pipeline

__all__ = ["Pipeline", "Document", "Sentence", "Token", "Word"]
__version__ = "0.1.0"
