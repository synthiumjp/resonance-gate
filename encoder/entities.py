"""Deterministic realistic entity/relation string sets for E3 measurements.

Deliberately includes confusable families: shared first names with role
qualifiers ("Tom (brother)" / "Tom (colleague)"), near-collision surnames
(Baker/Barker/Becker, Chen/Cheng), sibling org names ("Acme Labs" /
"Acme Analytics"), and near-synonym relations ("works at" / "is employed by",
"lives in" / "resides in"). Generation is seeded and order-stable.
"""

import numpy as np

FIRST = [
    "Tom", "Anna", "James", "Maria", "David", "Sarah", "Michael", "Emma",
    "John", "Sofia", "Robert", "Laura", "Daniel", "Alice", "Peter", "Nina",
    "Chris", "Julia", "Mark", "Elena", "Paul", "Clara", "Simon", "Ruth",
    "Victor", "Iris", "Oscar", "Maya", "Felix", "Nora", "Hugo", "Lena",
    "Adam", "Zoe", "Leo", "Ivy", "Max", "Ella", "Sam", "Grace",
]
LAST = [
    "Baker", "Barker", "Becker", "Carter", "Chen", "Cheng", "Chang", "Diaz",
    "Evans", "Fischer", "Fisher", "Garcia", "Hansen", "Hanson", "Ito", "Jones",
    "Johnson", "Johansson", "Kim", "Klein", "Kline", "Lopez", "Lowe", "Meyer",
    "Meier", "Nguyen", "Novak", "Olsen", "Olson", "Park", "Patel", "Quinn",
    "Reyes", "Rios", "Schmidt", "Schmitt", "Silva", "Sousa", "Souza", "Tran",
    "Vogel", "Weber", "Webber", "Wong", "Wang", "Yang", "Yuan", "Zhang",
    "Zheng", "Ziegler",
]
QUALIFIER = [
    "brother", "colleague", "neighbour", "cousin", "manager", "dentist",
    "landlord", "friend from work", "friend from the gym", "old classmate",
    "sister-in-law", "accountant",
]
ORG_A = [
    "Acme", "Apex", "Atlas", "Nova", "Vertex", "Orion", "Zenith", "Delta",
    "Summit", "Pioneer", "Cascade", "Beacon", "Harbor", "Quarry", "Meridian",
]
ORG_B = [
    "Labs", "Analytics", "Logistics", "Systems", "Consulting", "Dynamics",
    "Robotics", "Foods", "Energy", "Media",
]
CITY = [
    "Springfield (IL)", "Springfield (MA)", "Portland (OR)", "Portland (ME)",
    "Cambridge (UK)", "Cambridge (MA)", "Richmond", "Ridgemont", "Riverton",
    "Riverside", "Lakewood", "Lakeside", "Oakland", "Oakville", "Fairview",
    "Fairfield", "Georgetown", "Germantown", "Clinton", "Clifton", "Ashland",
    "Ashford", "Milton", "Melton", "Dayton", "Drayton", "Salem", "Selma",
    "Aurora", "Antioch", "Bristol", "Boston", "Berlin", "Dublin", "Lisbon",
    "Madrid", "Geneva", "Genoa", "Vienna", "Verona",
]

RELATIONS10 = [
    "works at", "is employed by",      # near-synonym pair (jobs)
    "lives in", "resides in",          # near-synonym pair (residence)
    "was born in", "manages", "reports to",
    "is married to", "is a sibling of", "studied at",
]


def _pools():
    persons = [f"{f} {l}" for f in FIRST for l in LAST]           # 2000
    qualified = [f"{f} ({q})" for f in FIRST for q in QUALIFIER]  # 480
    orgs = [f"{a} {b}" for a in ORG_A for b in ORG_B]             # 150
    return persons, qualified, orgs, list(CITY)


def make_entities(n, seed, mix=(0.55, 0.2, 0.15, 0.1)):
    """n unique entity strings: ~55% full-name persons, 20% qualified first
    names, 15% orgs, 10% cities (clipped to pool sizes; remainder from
    persons). Seeded shuffle inside each pool."""
    rng = np.random.default_rng(seed)
    pools = _pools()
    counts = [min(int(round(n * f)), len(p)) for f, p in zip(mix, pools)]
    counts[0] += n - sum(counts)  # remainder from the person pool
    if counts[0] > len(pools[0]):
        raise ValueError(f"cannot draw {n} entities from the pools")
    out = []
    for pool, c in zip(pools, counts):
        idx = rng.permutation(len(pool))[:c]
        out.extend(pool[i] for i in idx)
    rng.shuffle(out)
    return out
