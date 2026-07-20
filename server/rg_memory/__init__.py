"""rg-memory: a thin, LLM-free MCP server over the rg-1.1 VSA memory
substrate. No mouth, no extractor, no judge — pure substrate + gate +
registry. The only model present is the registry's MiniLM sentence-embedding
ENCODER (string -> fixed vector); it is non-generative and cannot fabricate
text or facts."""

__version__ = "0.1.0"
