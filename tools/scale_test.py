"""Does the memory still refuse and still find as it grows?

2026-10-02. The dogfood store has ~40 facts; a real user has thousands after
a few months. Ledger 5o already showed an absolute score floor that was
clean at 14 nodes and leaked at 38. This puts N filler statements IN FRONT of
the dogfood conversations and re-asks dogfood's questions at each size.

The filler is generated from templates and avoids every topic the
never-mentioned and unknown-attribute questions ask about (birthdays,
salary, gyms, films, pets, cars...), so a change in refusal is caused by the
size of the store and nothing else. Filler never states a home, job, diet
or relationship for the user, so it cannot replace a dogfood fact.

    python tools/scale_test.py --sizes 0 250 1000 2500
"""
import argparse
import os
import random
import re
import statistics
import sys
import tempfile
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "tools"))
import dogfood as D  # noqa: E402

NAMES = """Ana Ben Chloe Dev Elif Femi Gus Hana Ivo Jun Kofi Lena Milo Nia Omar
Pia Quin Rosa Sven Tara Umar Vera Wes Xia Yuri Zoe Arlo Bea Cyrus Dalia""".split()
PLACES = """Bruges Hobart Kyoto Porto Ghent Tromso Bergen Lyon Split Ronda Graz
Bled Cusco Hue Oaxaca Galway Matera Tallinn Riga Cork Bath Leiden Nara Ubud
Kotor Sintra Hallstatt Colmar Gdansk Ohrid""".split()
FOODS = """ramen paella dumplings pho laksa tacos gnocchi risotto bibimbap
shakshuka pierogi falafel curry souvlaki empanadas""".split()
BOOKS = """Middlemarch Dune Beloved Emma Ulysses Rebecca Kindred Persuasion
Solaris Stoner Piranesi Circe Hamnet Gilead Atonement""".split()
BANDS = """Radiohead Bjork Khruangbin Portishead Low Slowdive Wilco Beirut Air
Stereolab Talk Talk Grizzly Bear Phoenix Caribou Bonobo""".split()
SERVICES = """search notifications reporting ingest scheduler gateway audit
export onboarding pricing""".split()
TECH = """Kotlin Elixir Python TypeScript Scala Haskell Ruby Java Clojure Zig""".split()
SHOPS = ["market", "hardware store", "bookshop", "bakery", "deli", "op shop",
         "nursery"]
ITEMS = ["a rug", "a lamp", "some paint", "a kettle", "a desk chair", "a shelf",
         "some seeds", "a frying pan", "a backpack", "a notebook"]
SPORTS = """football cricket tennis basketball rugby netball hockey""".split()
WHEN = ["last week", "on Saturday", "a while ago", "in March", "last month",
        "on the weekend", "yesterday", "in the spring"]

TEMPLATES = [
    lambda r: f"I went to {r.choice(PLACES)} {r.choice(WHEN)}.",
    lambda r: f"My colleague {r.choice(NAMES)} is working on the "
              f"{r.choice(SERVICES)} project.",
    lambda r: f"I've been reading {r.choice(BOOKS)}.",
    lambda r: f"We had {r.choice(FOODS)} for dinner {r.choice(WHEN)}.",
    lambda r: f"The {r.choice(SERVICES)} service uses {r.choice(TECH)}.",
    lambda r: f"My friend {r.choice(NAMES)} lives in {r.choice(PLACES)}.",
    lambda r: f"I listened to {r.choice(BANDS)} on the train.",
    lambda r: f"I bought {r.choice(ITEMS)} from the {r.choice(SHOPS)}.",
    lambda r: f"{r.choice(NAMES)} recommended {r.choice(BOOKS)} to me.",
    lambda r: f"I watched the {r.choice(SPORTS)} with {r.choice(NAMES)} "
              f"{r.choice(WHEN)}.",
    lambda r: f"I fixed a bug in the {r.choice(SERVICES)} service.",
    lambda r: f"My neighbour {r.choice(NAMES)} grows tomatoes.",
    # combinatorial, so a large store has thousands of DISTINCT facts
    lambda r: f"I went to {r.choice(PLACES)} with {r.choice(NAMES)} "
              f"{r.choice(WHEN)}.",
    lambda r: f"{r.choice(NAMES)} cooked {r.choice(FOODS)} for "
              f"{r.choice(NAMES)} {r.choice(WHEN)}.",
    lambda r: f"My colleague {r.choice(NAMES)} moved the {r.choice(SERVICES)} "
              f"service to {r.choice(TECH)}.",
    lambda r: f"{r.choice(NAMES)} lent me {r.choice(BOOKS)} {r.choice(WHEN)}.",
    lambda r: f"I saw {r.choice(BANDS)} play in {r.choice(PLACES)} "
              f"{r.choice(WHEN)}.",
    lambda r: f"My friend {r.choice(NAMES)} visited {r.choice(PLACES)} and "
              f"loved the {r.choice(FOODS)}.",
]
# what the filler must never mention (the unseen / unknown-attribute topics)
_FORBIDDEN = re.compile(r"\b(birthday|salary|gym|film|movie|dog|cat|car|"
                        r"born|university|children|kids|blood|breed|colour|"
                        r"scooter|bike|coffee|tea|commute|home|job|work)\b",
                        re.I)


def filler(n, seed=20261002):
    r = random.Random(seed)
    turns = []
    while len(turns) < n:
        t = r.choice(TEMPLATES)(r)
        if not _FORBIDDEN.search(t):
            turns.append({"role": "user", "content": t})
    return [turns[i:i + 10] for i in range(0, len(turns), 10)]


def run(size, v3=True):
    tmp = tempfile.mkdtemp(prefix=f"rg-scale-{size}-")
    os.environ["RG_MEMORY_DIR"] = os.path.join(tmp, "mem")
    os.environ["SOURCEDRECALL_STATE"] = os.path.join(tmp, "state")
    os.environ["SOURCEDRECALL_BROWSER_PORT"] = "0"
    os.environ["SOURCEDRECALL_OWNER"] = D.OWNER
    os.environ["RG_PROFILE_V3"] = "1" if v3 else "0"
    os.makedirs(os.environ["RG_MEMORY_DIR"], exist_ok=True)
    os.makedirs(os.environ["SOURCEDRECALL_STATE"], exist_ok=True)
    sys.path.insert(0, os.path.join(_ROOT, "server"))
    sys.path.insert(0, _ROOT)
    from sourcedrecall import profile_memory as pm
    pm._state.update({"mem": None, "audit_pass": None, "needs_reload": False,
                      "uncached_turns": None, "transcripts": None})
    t0 = time.time()
    for i, sess in enumerate(filler(size)):
        pm.profile_ingest(sess, conversation_id=f"filler-{i}",
                          title=f"filler {i}", owner_name=D.OWNER,
                          date=f"2025-{1 + i % 12:02d}-{1 + i % 28:02d}")
    for i, sess in enumerate(D.SESSIONS):
        pm.profile_ingest(sess, title=f"session {i+1}", owner_name=D.OWNER)
    ingest_s = time.time() - t0
    st = pm.profile_status()
    pm.profile_recall("warm up")
    lat = []

    def ask(q):
        a = time.time()
        out = pm.profile_recall(q)
        lat.append(time.time() - a)
        return out

    r1 = pool = 0
    misses = []
    for q, needle in D.ANSWERABLE.items():
        out = ask(q)
        got = D.facts_of(out)
        r1 += bool(got) and needle.lower() in got[0].lower()
        hit = any(needle.lower() in g.lower() for g in got)
        pool += hit
        if not hit:
            misses.append((q, out.get("gate") or (got[0][:70] if got else "-")))
    leaks = []
    for q in D.UNSEEN + D.UNSEEN_NAMED:
        out = ask(q)
        got = D.facts_of(out)
        if not out.get("abstain") or got:
            leaks.append((q, got[0][:70] if got else "-"))
    partial = sum(1 for q, _, _ in D.PARTIAL_KNOWLEDGE if ask(q).get("abstain"))
    ho_ok = sum(1 for q, needle in D.HELDOUT_ANSWERABLE.items()
                if any(needle.lower() in g.lower() for g in D.facts_of(ask(q))))
    ho_partial = sum(1 for q, _, _ in D.HELDOUT_PARTIAL if ask(q).get("abstain"))
    n_unseen = len(D.UNSEEN) + len(D.UNSEEN_NAMED)
    return {
        "filler": size, "facts": st["asserted"] + st["provisional"],
        "rank1": f"{r1}/{len(D.ANSWERABLE)}", "pool": f"{pool}/{len(D.ANSWERABLE)}",
        "abstain": f"{n_unseen - len(leaks)}/{n_unseen}",
        "partial": f"{partial}/{len(D.PARTIAL_KNOWLEDGE)}",
        "ho_found": f"{ho_ok}/{len(D.HELDOUT_ANSWERABLE)}",
        "ho_refused": f"{ho_partial}/{len(D.HELDOUT_PARTIAL)}",
        "median_ms": round(1000 * statistics.median(lat)),
        "p95_ms": round(1000 * sorted(lat)[int(0.95 * (len(lat) - 1))]),
        "ingest_s": round(ingest_s),
        "leaks": leaks, "misses": misses,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", type=int, nargs="+", default=[0, 250, 1000, 2500])
    a = ap.parse_args()
    cols = ["filler", "facts", "rank1", "pool", "abstain", "partial",
            "ho_found", "ho_refused", "median_ms", "p95_ms", "ingest_s"]
    rows = []
    for n in a.sizes:
        row = run(n)
        rows.append(row)
        print(" ".join(f"{c}={row[c]}" for c in cols), flush=True)
        for q, got in row["leaks"]:
            print(f"    LEAK  {q} -> {got}", flush=True)
        for q, got in row["misses"]:
            print(f"    MISS  {q} -> {got}", flush=True)
    print()
    print("| " + " | ".join(cols) + " |")
    print("|" + "---|" * len(cols))
    for row in rows:
        print("| " + " | ".join(str(row[c]) for c in cols) + " |")


if __name__ == "__main__":
    main()
