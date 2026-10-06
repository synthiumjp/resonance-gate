import json, sys, collections
rows = [json.loads(l) for l in open(sys.argv[1])]
SYS = list(rows[0]["sys"]) if rows else ["ours", "bm25", "bge"]
KS = [1, 3, 5, 10]
def sess_metrics(r, s, k):
    top = set(r["sys"][s]["sessions"][:k]); g = set(r["answer_session_ids"])
    return (float(any(x in top for x in g)), float(all(x in top for x in g)))
def turn_metrics(r, s, k):
    top = {tuple(x) for x in r["sys"][s]["turns"][:k]}; g = {tuple(x) for x in r["gold_turns"]}
    return (float(any(x in top for x in g)), float(all(x in top for x in g)))
def table(sub, label, fn, ks):
    n = len(sub)
    print(f"\n{label} (n={n})")
    print("| system | " + " | ".join(f"any@{k} | all@{k}" for k in ks) + " |")
    print("|---|" + "---|" * (2 * len(ks)))
    for s in SYS:
        cells = []
        for k in ks:
            m = [fn(r, s, k) for r in sub]
            cells += [f"{100*sum(x[0] for x in m)/n:.1f}", f"{100*sum(x[1] for x in m)/n:.1f}"]
        print(f"| {s} | " + " | ".join(cells) + " |")
na = [r for r in rows if not r["abs"]]
print(f"questions run: {len(rows)} (non-abstention {len(na)})")
for name, sub in (("non-abstention", na), ("all incl. abstention", rows)):
    table(sub, f"SESSION-LEVEL, {name}, all types", sess_metrics, KS)
    table([r for r in sub if r["question_type"] != "single-session-assistant"],
          f"SESSION-LEVEL, {name}, excluding single-session-assistant", sess_metrics, KS)
for t in sorted({r["question_type"] for r in rows}):
    table([r for r in na if r["question_type"] == t], f"SESSION-LEVEL, non-abstention, {t}", sess_metrics, KS)
# short lists
for s in ("ours",):
    c = collections.Counter(min(len(r["sys"][s]["sessions"]), 10) for r in rows)
    print(f"\n{s}: distinct sessions returned from top-50 messages (capped at 10): {dict(sorted(c.items()))}")
    print(f"{s}: unmatched hits (text not mapped to a turn): {sum(r['sys'][s]['unmatched'] for r in rows)} of {sum(r['sys'][s]['n_hits'] for r in rows)}")
# turn level
tl = [r for r in na if r["gold_turns"]]
table(tl, "TURN-LEVEL (user turns with has_answer), non-abstention, questions with >=1 gold user turn", turn_metrics, [1, 3, 5, 10, 50])
for t in sorted({r["question_type"] for r in tl}):
    table([r for r in tl if r["question_type"] == t], f"TURN-LEVEL {t}", turn_metrics, [5, 10, 50])
print("\nnon-abstention questions with no gold user turn:", collections.Counter(r["question_type"] for r in na if not r["gold_turns"]))
print("ingest s/q mean:", sum(r["ingest_s"] for r in rows) / len(rows), " total_s:", sum(r["total_s"] for r in rows))
