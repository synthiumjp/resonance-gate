"""Route inference-type questions to abstention (entry 179).

The strict-judge profile splits HaluMem into two different tasks:
  retrieval categories (73%)  64.1% correct / 15.0% hallucination
  inference categories (27%)  11.2% correct / 46.2% hallucination
RG is an evidence layer -- it retrieves receipted facts and hands composition
to the client. On questions that ask the MEMORY to generalise or infer, the
composer attempts it anyway and fabricates on ~46%. Meanwhile Memory Boundary
shows the abstention machinery works when pointed at the right questions:
95.8% correct, 4.2% hallucination, zero omissions.

So: detect inference questions and abstain on them. Two rules make this honest
rather than a leaderboard trick:

1. The gold `question_type` is NEVER used at decision time. It is a LABEL for
   validating the detector, nothing more. A product does not get told the
   question's category, so neither does the gate. The detector reads the
   question string only -- no context, no answer, no gold.
2. Every gain is compared against RANDOM abstention at MATCHED COVERAGE.
   Abstaining on any 27% of questions lowers hallucination; the only thing
   worth shipping is abstention that beats the coin flip at the same coverage.
   This is the discipline entry 168 established when an AUROC gain failed to
   convert into a frontier gain.
"""
import re

# Inference questions ask what COULD/SHOULD follow from memory, or ask the
# system to synthesise across facts. Retrieval questions ask what IS stored.
# Kept as readable patterns rather than a trained model: it is auditable, has
# no fitting budget to overfit with, and the signal is largely modal verbs.
_INFER_PAT = [
    (r"\b(could|should|would|might|may)\b", 3.0),
    (r"\bhow (might|could|would|should)\b", 3.0),
    (r"\b(recommend|suggest|advice|advise)\b", 2.5),
    (r"\b(to (enhance|improve|maximis|maximiz|optimis|optimiz|benefit))\b", 2.5),
    (r"\b(what kind of|what type of|what sort of)\b.*\b(could|would|should|might)\b", 2.0),
    (r"\b(based on|given|considering|drawing on)\b.*\b(what|how)\b", 1.5),
    (r"\b(implication|insight|pattern|theme|overall|in general|generally)\b", 1.5),
    (r"\b(combine|integrate|incorporate|apply|leverage)\b", 1.5),
    (r"\bwhy (might|would|could)\b", 2.0),
]
# Strong retrieval markers pull back toward answering -- a direct slot lookup
# should never be gated just because it contains a soft word.
_RETRIEVE_PAT = [
    (r"^what (is|was|are|were)\b", 2.0),
    (r"\b(birth date|middle name|full name|phone|email|address|age)\b", 3.0),
    (r"\bas of \w+", 1.5),
    (r"\b(did|does|is|was|has|have)\b.*\?$", 1.0),
    (r"\bhow many\b", 1.5),
    (r"\bwhen (did|was|is)\b", 1.5),
    (r"\bwhere (did|does|is|was)\b", 1.5),
]

_INFER_RX = [(re.compile(p, re.I), w) for p, w in _INFER_PAT]
_RETRIEVE_RX = [(re.compile(p, re.I), w) for p, w in _RETRIEVE_PAT]


def inference_score(question):
    """Higher = more likely to require inference beyond stored evidence.

    Deliberately a score rather than a boolean, so the operating threshold is a
    dial on the risk-coverage frontier instead of a hardcoded policy."""
    q = " ".join(str(question or "").split())
    s = 0.0
    for rx, w in _INFER_RX:
        if rx.search(q):
            s += w
    for rx, w in _RETRIEVE_RX:
        if rx.search(q):
            s -= w
    return s


def is_inference(question, threshold=1.0):
    return inference_score(question) >= threshold


ABSTAIN = "Unknown."
