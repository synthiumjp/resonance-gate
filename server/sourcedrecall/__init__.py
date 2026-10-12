"""sourcedrecall: a thin, LLM-free MCP server over the Resonance Gate rg-1.1
VSA memory substrate. No mouth, no extractor, no judge — pure substrate +
gate + registry. The only model present is the registry's MiniLM
sentence-embedding ENCODER (string -> fixed vector); it is non-generative and
cannot fabricate text or facts."""

# 2026-10-12 (review 4.5): was a fixed "0.1.0" while the package said 0.5.2
try:
    from importlib.metadata import version as _v
    __version__ = _v("sourcedrecall")
except Exception:
    __version__ = "unknown"
