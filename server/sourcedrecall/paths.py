"""Where sourcedrecall keeps its data. Shared by the MCP server and the
Claude Code hooks, so a hook never has to import the server (and its `mcp`
dependency) just to find the memory. Read from the environment at CALL time,
not import time."""
import os


def state_dir():
    return os.environ.get("SOURCEDRECALL_STATE",
                          os.path.expanduser("~/.sourcedrecall"))


def default_memory_dir():
    """2026-10-02, from the new-user install test: RG_MEMORY_DIR was required
    and documented only in a docstring, so the first profile_* call failed.
    The LIBRARY still refuses to guess (profile_memory._data_dir raises, so a
    forgetful test can never touch a real user's data); the server and the
    hooks -- what a person actually runs -- default it beside
    SOURCEDRECALL_STATE."""
    if not os.environ.get("RG_MEMORY_DIR"):
        d = os.path.join(state_dir(), "conversations")
        os.makedirs(d, exist_ok=True)
        os.environ["RG_MEMORY_DIR"] = d
    return os.environ["RG_MEMORY_DIR"]
