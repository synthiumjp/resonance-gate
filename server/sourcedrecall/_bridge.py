"""Where the memory code lives (2026-10-04): the repository checkout when
there is one (experiments/p2 and rgx/, for development), else the copy a
wheel carries in sourcedrecall/_core (tools/build_wheel.py). RG_ROOT
overrides the checkout location."""
import os

_HERE = os.path.dirname(os.path.abspath(__file__))


def code_roots():
    """-> (root holding the rgx package, directory of the flat p2 modules)."""
    repo = os.environ.get("RG_ROOT", os.path.dirname(os.path.dirname(_HERE)))
    p2 = os.path.join(repo, "experiments", "p2")
    if os.path.isdir(p2) and os.path.isdir(os.path.join(repo, "rgx")):
        return repo, p2
    core = os.path.join(_HERE, "_core")
    return core, core
