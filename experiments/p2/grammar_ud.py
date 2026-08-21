"""Moved into the `rgx` package (v0.1.0). Shim -- see rgx/parse.py."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
from rgx.parse import *  # noqa: F401,F403
