#!/usr/bin/env python
"""RG minimal REPL: input -> extraction (write) -> query encoding -> gate ->
controller -> speak. E3 Part 4. Everything gate-governed is template-
rendered; the mouth only parses utterances and (optionally) adds connective
text. CPU inference is the accepted path.

Usage: .venv/bin/python rg_chat.py [--llm-wrapper] [--seed 42]
"""

import argparse
import os
import re
import sys

_R = os.path.dirname(os.path.abspath(__file__))
for _p in (_R, f"{_R}/substrate", f"{_R}/gate", f"{_R}/encoder", f"{_R}/mouth"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from registry import Registry
from write_path import Memory, extract_triples
from speak import ABSTAIN_TEXT, ACK_TEXT, ECHO_FAIL_TEXT, RECOLLECT_TEXT, render, speak

CANONICAL_RELATIONS = ["works at", "lives in", "was born in", "manages",
                       "reports to", "is married to", "is a sibling of",
                       "studied at", "is scheduled at"]
WRITE_MERGE_COSINE = 0.95  # entities: merge only near-exact string variants
REL_MERGE_COSINE = 0.80    # relations: canonicalise paraphrases

QUESTION_RE = re.compile(
    r"^(where|who|whom|when|what|which|does|do|did|is|are|can|could|has|have)\b",
    re.IGNORECASE)
CORRECTION_RE = re.compile(r"^(actually|no,|correction[:,]?|wait,)", re.IGNORECASE)
FORGET_RE = re.compile(r"^(forget|delete|remove)\b", re.IGNORECASE)

QUERY_SYSTEM = """You turn one question into the (subject | relation) being asked about.
Output ONLY one line of this exact form: (subject | relation)
relation must be one of: works at, lives in, was born in, manages, reports to,
is married to, is a sibling of, studied at, is scheduled at.
Keep the speaker's own words for names ("my brother Tom" -> Tom (brother)).
Examples:
"Where does Elizabeth Carter live?" -> (Elizabeth Carter | lives in)
"Where does my brother Tom work?" -> (Tom (brother) | works at)
"Who does Sarah Kim manage?" -> (Sarah Kim | manages)
"When is my meeting?" -> (my meeting | is scheduled at)
"Does Maria Garcia live in Lisbon?" -> (Maria Garcia | lives in)
"Where did Peter Yang study?" -> (Peter Yang | studied at)"""

def parse_question(text):
    """(subject, relation) from the mouth's parse. Tolerant of the wrapper
    parens being dropped and of parens INSIDE fields ("Tom (brother)")."""
    from llm import generate
    raw = generate(QUERY_SYSTEM, f'"{text}"', max_tokens=48, temperature=0.0)
    for line in raw.splitlines():
        line = line.strip()
        if "|" not in line:
            continue
        if line.startswith("(") and line.endswith(")"):
            line = line[1:-1]
        parts = [p.strip() for p in line.split("|")]
        if len(parts) == 2 and all(parts):
            return parts[0], parts[1].lower()
    return None


class ChatSession:
    def __init__(self, use_llm_wrapper=False, calib=None, seed=42):
        self.ent = Registry([])
        self.rel = Registry(CANONICAL_RELATIONS)
        self.mem = Memory(self.ent, self.rel, calib=calib)
        self.use_llm_wrapper = use_llm_wrapper
        self.seed = seed
        self.n_turn = 0

    # ------------------------------------------------------------ helpers

    def _canon(self, term, reg, thr):
        if term in reg:
            return term
        if len(reg) == 0:
            reg.add([term])
            return term
        name, c = reg.resolve(term, top=1)[0]
        if c >= thr:
            return name
        reg.add([term])
        return term

    def _canon_triple(self, t):
        s, r, o = t
        return (self._canon(s, self.ent, WRITE_MERGE_COSINE),
                self._canon(r, self.rel, REL_MERGE_COSINE),
                self._canon(o, self.ent, WRITE_MERGE_COSINE))

    def _active_objects(self, subj, rel):
        return [meta["triple"][2] for i, meta in enumerate(self.mem.store.meta)
                if self.mem.store.active[i] and meta
                and meta["triple"][:2] == (subj, rel)]

    def _speak(self, action, tag=None, payload=None):
        return speak(action, tag=tag, payload=payload,
                     use_llm=self.use_llm_wrapper,
                     llm_seed=self.seed * 1000 + self.n_turn)

    # ------------------------------------------------------------ the loop

    def turn(self, text):
        """One conversational turn. Returns (reply, info) where info records
        the routing: action, tag, opinion, and any records touched."""
        self.n_turn += 1
        text = text.strip()

        if FORGET_RE.match(text):
            target = FORGET_RE.sub("", text).strip().rstrip(".?") + "?"
            parsed = parse_question(target)
            if not parsed:
                return "I couldn't tell which fact to remove.", {"action": "forget-failed"}
            subj = self._canon(parsed[0], self.ent, WRITE_MERGE_COSINE)
            rel = self._canon(parsed[1], self.rel, REL_MERGE_COSINE)
            objs = self._active_objects(subj, rel)
            for o in objs:
                self.mem.forget(subj, rel, o)
            reply = "Done — I've removed that." if objs else "I had nothing stored to remove."
            return reply, {"action": "forget", "removed": [(subj, rel, o) for o in objs]}

        if QUESTION_RE.match(text) or text.endswith("?"):
            parsed = parse_question(text)
            if not parsed:
                return ABSTAIN_TEXT, {"action": "abstain", "tag": None, "note": "unparsed"}
            q = self.mem.query(*parsed)
            if q.action == "answer":
                reply = self._speak("answer", payload=(q.record, q.provenance))
            elif q.action == "deliberate":
                payload = q.candidates
                reply = self._speak("deliberate", tag=q.tag, payload=payload)
            elif q.action == "recollect":
                reply = RECOLLECT_TEXT
            else:
                reply = self._speak("abstain")
            return reply, {"action": q.action, "tag": q.tag, "op": q.op,
                           "record": q.record, "candidates": q.candidates,
                           "m_ref": q.m_ref, "m_l2": q.m_l2, "parsed": parsed}

        correction = bool(CORRECTION_RE.match(text))
        body = CORRECTION_RE.sub("", text).strip() if correction else text
        if correction:  # "lives in Vienna now." — the current state IS asserted
            body = re.sub(r"\s+now([.!?]?)$", r"\1", body)
        triples = [self._canon_triple(t) for t in extract_triples(body)]
        if not triples:
            return "Okay.", {"action": "no-op", "note": "nothing extracted"}

        written, superseded, rejected = [], [], []
        for s, r, o in triples:
            if correction:
                olds = [x for x in self._active_objects(s, r) if x != o]
                if olds:
                    res = self.mem.supersede(s, r, olds[0], o)
                    (superseded if res.accepted else rejected).append((s, r, o))
                    continue
            res = self.mem.write(s, r, o, provenance="user-stated")
            (written if res.accepted else rejected).append((s, r, o))

        parts = [ACK_TEXT.format(fact=render(t).rstrip(".")) for t in written]
        parts += [f"Updated: {render(t).rstrip('.')}." for t in superseded]
        parts += [ECHO_FAIL_TEXT for _ in rejected]
        return " ".join(parts), {"action": "write", "written": written,
                                 "superseded": superseded, "rejected": rejected}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm-wrapper", action="store_true",
                    help="mouth adds connective lead-ins (slower)")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    print("RG chat (E3). Ctrl-D to exit. Seed:", args.seed)
    session = ChatSession(use_llm_wrapper=args.llm_wrapper, seed=args.seed)
    while True:
        try:
            text = input("you> ").strip()
        except EOFError:
            print()
            break
        if not text:
            continue
        reply, info = session.turn(text)
        tag = f"/{info.get('tag')}" if info.get("tag") else ""
        print(f"rg [{info['action']}{tag}]> {reply}")


if __name__ == "__main__":
    main()
