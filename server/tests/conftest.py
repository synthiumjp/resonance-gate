import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("RG_MEMORY_BROWSER_PORT", "0")


import pytest


@pytest.fixture
def service(tmp_path):
    from rg_memory.service import MemoryService
    return MemoryService(str(tmp_path / "state"))
