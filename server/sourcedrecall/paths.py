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


def project_scope(path):
    """The project a directory belongs to: its git root if it is inside a
    repository, else the directory itself (2026-10-02, scoping). None for
    no path. Subdirectories of one repository are one project."""
    if not path:
        return None
    p = os.path.realpath(os.path.expanduser(str(path)))
    cur = p
    while True:
        if os.path.exists(os.path.join(cur, ".git")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return p
        cur = parent


def current_scope(explicit=None):
    """The scope to read in: an explicit one, else SOURCEDRECALL_SCOPE, else
    the project Claude Code is running in (CLAUDE_PROJECT_DIR, which it sets
    for MCP servers and hooks). None means no scoping: everything is
    visible. SOURCEDRECALL_SCOPING=0 turns scoping off."""
    if os.environ.get("SOURCEDRECALL_SCOPING") == "0":
        return None
    raw = (explicit or os.environ.get("SOURCEDRECALL_SCOPE")
           or os.environ.get("CLAUDE_PROJECT_DIR"))
    return project_scope(raw) if raw else None


def parser_models_dir():
    """Where setup installs the PyTorch-free parser's models (2026-10-05)."""
    return os.environ.get("SOURCEDRECALL_PARSER_MODELS",
                          os.path.join(state_dir(), "parser-models"))


def use_installed_parser():
    """Point rgx at the installed stanza_ort models, if there are any (rgx
    falls back to Stanza on PyTorch otherwise)."""
    d = parser_models_dir()
    if (not os.environ.get("RGX_PARSER_MODELS")
            and os.path.exists(os.path.join(d, "config.json"))):
        os.environ["RGX_PARSER_MODELS"] = d
