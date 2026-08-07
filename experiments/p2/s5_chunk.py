"""Split one user's eval artifact into session chunks so the judge checkpoints.

evaluation.py writes its per-user checkpoint to tmp2/<uuid>.json only AFTER
process_user finishes every judge call for that user. On a full 20-user run
that is fine -- a crash loses at most 1/20th. On the S5 A/B, which judges ONE
user (~2,400 calls, hours of GPU), it means a crash at 90% loses everything.

Chunking is done here rather than by patching evaluation.py because the judge
must stay byte-identical to the official harness. It is safe to do:
aggregate_eval_results pools records with a flat sum over every user line
(recall = scores/num, no per-user mean anywhere), and every metric is computed
per SESSION -- integrity against that session's extracted_memories, accuracy
against that session's dialogue, QA against that session's questions. Splitting
the session list across lines therefore changes the checkpoint granularity and
nothing else. Verified by construction: chunk_all() partitions sessions with no
overlap and no drop.

Usage:
    python s5_chunk.py IN.jsonl OUT.jsonl --per 9
"""
import argparse
import json


def chunk_user(user, per):
    """One user dict -> list of user dicts, sessions partitioned in order."""
    sessions = user["sessions"]
    out = []
    for c, start in enumerate(range(0, len(sessions), per)):
        part = dict(user)
        part["uuid"] = f"{user['uuid']}#c{c}"
        part["user_name"] = f"{user.get('user_name', user['uuid'])}#c{c}"
        part["sessions"] = sessions[start:start + per]
        out.append(part)
    return out


def main(src, dst, per):
    n_in = n_out = n_sess_in = n_sess_out = 0
    with open(dst, "w", encoding="utf-8") as f_out:
        for line in open(src, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            user = json.loads(line)
            n_in += 1
            n_sess_in += len(user["sessions"])
            for part in chunk_user(user, per):
                f_out.write(json.dumps(part, ensure_ascii=False) + "\n")
                n_out += 1
                n_sess_out += len(part["sessions"])
    assert n_sess_in == n_sess_out, (n_sess_in, n_sess_out)
    print(f"{src} -> {dst}: {n_in} users / {n_sess_in} sessions "
          f"-> {n_out} chunks / {n_sess_out} sessions (no loss)")
    return n_out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--per", type=int, default=9)
    a = ap.parse_args()
    main(a.src, a.dst, a.per)
