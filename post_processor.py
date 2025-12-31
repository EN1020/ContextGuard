from __future__ import annotations

from dataclasses import dataclass
from typing import List, Set, Tuple, Literal

Risk = Literal["LOW", "MEDIUM", "HIGH"]


@dataclass(frozen=True)
class PostProcessConfig:
    """
    Deterministic guardrails to correct LLM outputs.
    """
    # keyword heuristics (very simple on Day 4; can evolve later)
    injection_keywords: Tuple[str, ...] = (
        "ignore previous",
        "ignore above",
        "disregard",
        "override",
        "system prompt",
        "reveal",
        "secret",
        "bypass",
    )
    vague_keywords: Tuple[str, ...] = (
        "summarize this",
        "do it",
        "help me",
        "tell me about",
    )


def _contains_any(haystack: str, needles: Tuple[str, ...]) -> bool:
    s = (haystack or "").lower()
    return any(n in s for n in needles)


def post_process(
    *,
    user_prompt: str,
    context: str,
    llm_risk_level: Risk,
    llm_detected_issues: List[str],
    llm_recommendations: List[str],
    cfg: PostProcessConfig = PostProcessConfig(),
) -> tuple[Risk, List[str], List[str], float]:
    """
    Returns:
      - final_risk_level
      - final_detected_issues
      - final_recommendations
      - final_context_score (rule-adjusted)
    """

    issues: Set[str] = set(llm_detected_issues or [])
    recs: List[str] = list(llm_recommendations or [])
    final_risk: Risk = llm_risk_level

    # --- Rule 1: context scoring (deterministic, simple)
    ctx = (context or "").strip()
    if not ctx:
        context_score = 0.0
        issues.add("missing_context")
    else:
        # crude heuristic by length; later can use embeddings
        context_score = 0.4 if len(ctx) < 80 else 0.7

    # --- Rule 2: injection detection (override to HIGH)
    if _contains_any(user_prompt, cfg.injection_keywords):
        issues.add("prompt_injection")
        issues.add("system_override_attempt")
        final_risk = "HIGH"

    # --- Rule 3: ambiguity detection (at least MEDIUM)
    if _contains_any(user_prompt, cfg.vague_keywords):
        issues.add("ambiguous_instruction")
        if final_risk != "HIGH":
            final_risk = "MEDIUM"

    # --- Rule 4: consistency lock
    if final_risk in ("HIGH", "MEDIUM") and len(issues) == 0:
        issues.add("unclassified_risk_signal")
    if final_risk == "LOW" and len(issues) > 0:
        # If LOW but issues exist, escalate to MEDIUM unless it's purely informational
        final_risk = "MEDIUM"

    # --- Rule 5: ensure recommendations exist when risk elevated
    if final_risk in ("HIGH", "MEDIUM") and len(recs) == 0:
        recs.append("Add stricter guardrails and clarify task requirements.")

    return final_risk, sorted(issues), recs, context_score
