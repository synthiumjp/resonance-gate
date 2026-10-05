"""Canonical, builtin-types-only dump of a Document (Stanza's or stanza_ort's), for comparison."""

def canon(doc):
    out = {"text": doc.text, "num_tokens": doc.num_tokens, "num_words": doc.num_words, "sents": []}
    for s in doc.sentences:
        toks = []
        for t in s.tokens:
            toks.append((tuple(t.id), t.text, t.misc, t.start_char, t.end_char, t.spaces_after, t.spaces_before,
                         tuple(w.id for w in t.words)))
        words = []
        for w in s.words:
            words.append({"id": w.id, "text": w.text, "upos": w.upos, "xpos": w.xpos, "feats": w.feats,
                          "lemma": w.lemma, "head": (None if w.head is None else int(w.head)),
                          "deprel": w.deprel, "deps": w.deps, "misc": w.misc,
                          "start_char": w.start_char, "end_char": w.end_char,
                          "parent": (tuple(w.parent.id) if w.parent is not None else None),
                          "sent_ok": w.sent is s})
        deps = [(h.id, r, w.id) for h, r, w in s.dependencies]
        out["sents"].append({"text": s.text, "index": s.index, "sent_id": s.sent_id, "tokens": toks,
                             "words": words, "deps": deps,
                             "tok_sent_ok": all(t.sent is s for t in s.tokens)})
    return out
