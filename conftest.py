import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
for p in (ROOT, os.path.join(ROOT, "substrate"), os.path.join(ROOT, "gate"),
          os.path.join(ROOT, "encoder"), os.path.join(ROOT, "mouth")):
    if p not in sys.path:
        sys.path.insert(0, p)
