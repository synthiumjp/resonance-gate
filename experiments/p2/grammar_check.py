"""Moved into the `rgx` package (v0.1.0). Kept as a shim so the
benchmark harness in this directory imports the SAME code the
package ships -- a second copy would drift, and the numbers in the
ledger are only meaningful if the shipped extractor is the measured
one."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
from rgx.check import *  # noqa: F401,F403
from rgx.check import _content, _stems  # noqa: F401
