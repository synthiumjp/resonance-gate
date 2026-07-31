"""Extractor-capability A/B, remote leg (entry 118 planned): re-extract dev
users with a LARGER qwen via an ollama endpoint (e.g. the M3 Ultra through an
SSH tunnel), into a separate cache namespace, then score with oracle.py --
the deterministic gold-in-store ceiling, no judge anywhere.

Faithful replica of dev_set.cmd_extract's resumable loop (same turn hashing,
same parse/retry contract via dev_set.extract_via_ollama), differing only in:
endpoint (RG_OLLAMA_URL), model (RG_EXTRACT_MODEL), cache template
(RG_CACHE_TEMPLATE). v5.1 system prompt always (SYSTEM_V5 imported directly).

Usage:
  RG_OLLAMA_URL=http://localhost:11435/api/chat RG_EXTRACT_MODEL=qwen3:32b \
  RG_CACHE_TEMPLATE='~/rg_private/halumem/dev/cache_u{i}_v5_32b.jsonl' \
  python extract_remote.py --users 10-12
"""
import argparse
import json
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import dev_set
from llm_profile import SYSTEM_V5

URL = os.environ.get("RG_OLLAMA_URL", "http://localhost:11435/api/chat")
MODEL = os.environ.get("RG_EXTRACT_MODEL", "qwen3:32b")
TEMPLATE = os.environ.get("RG_CACHE_TEMPLATE",
                          "~/rg_private/halumem/dev/cache_u{i}_v5_32b.jsonl")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--users", default="10-12")
    args = ap.parse_args()
    dev_set.OLLAMA_URL = URL          # reroute the module's client
    users = dev_set._load_users()
    print(f"endpoint={URL} model={MODEL} template={TEMPLATE}", flush=True)
    for uidx in dev_set._parse_users_arg(args.users):
        user = users[uidx]
        cache_path = dev_set._cache_path(uidx, TEMPLATE)
        cached = set()
        if os.path.exists(cache_path):
            for line in open(cache_path):
                try:
                    cached.add(json.loads(line)["h"])
                except Exception:
                    pass
        turns = list(dev_set._user_turns(user))
        todo = [(h, t) for h, t in turns if h not in cached]
        print(f"user {uidx}: {len(turns)} turns, {len(cached)} cached, "
              f"{len(todo)} to extract -> {cache_path}", flush=True)
        cf = open(cache_path, "a")
        t0 = time.monotonic()
        for n, (h, text) in enumerate(todo, 1):
            facts, latency, failed = dev_set.extract_via_ollama(
                text, model=MODEL, system=SYSTEM_V5)
            cf.write(json.dumps({"h": h, "f": facts}) + "\n")
            cf.flush()
            if n % 25 == 0:
                rate = n / (time.monotonic() - t0)
                print(f"  ...{n}/{len(todo)}  {rate:.2f} turns/s  "
                      f"ETA {((len(todo)-n)/rate)/60:.0f} min", flush=True)
        cf.close()
        print(f"user {uidx}: complete", flush=True)


if __name__ == "__main__":
    main()
