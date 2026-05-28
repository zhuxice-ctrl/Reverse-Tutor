"""Gate deciding whether a tutor turn's content may enter the knowledge graph.

Privacy principle (from design doc 22): store learning evidence, not life details;
do not persist by default when content is sensitive; let users disable extraction.
"""
from __future__ import annotations

from typing import Any

# Default sensitive keywords: if present in user input or the knowledge point,
# the turn is blocked from graph extraction.
KG_DEFAULT_BLACKLIST: tuple[str, ...] = (
    "身份证", "手机号", "电话", "家庭住址", "住址", "银行卡", "密码",
    "工资", "收入", "病", "诊断", "抑郁", "恋爱", "感情", "分手",
    "家人", "父母", "隐私",
)


def _contains_blacklisted(text: str, blacklist: tuple[str, ...] | list[str]) -> str | None:
    t = text or ""
    for kw in blacklist:
        kw = (kw or "").strip()
        if kw and kw in t:
            return kw
    return None


def should_extract(
    settings: dict[str, Any] | None,
    user_input: str,
    evaluation: dict[str, Any] | None,
    action: dict[str, Any] | None,
) -> tuple[bool, str]:
    """Return (allowed, reason).

    Rules (in order):
    1. settings.kg_extraction_enabled == False  -> (False, "disabled")
    2. empty knowledge_point                     -> (False, "no_kp")
    3. blacklist hit in user_input or kp         -> (False, "blacklisted:<kw>")
    4. privacy_level == "strict" AND no learning evidence -> (False, "strict_no_evidence")
    5. otherwise                                 -> (True, "allowed")
    """
    settings = settings or {}
    evaluation = evaluation or {}
    action = action or {}

    if settings.get("kg_extraction_enabled", True) is False:
        return False, "disabled"

    kp = (action.get("knowledge_point") or "").strip()
    if not kp:
        return False, "no_kp"

    blacklist = tuple(KG_DEFAULT_BLACKLIST) + tuple(settings.get("kg_blacklist") or [])
    hit = _contains_blacklisted(user_input, blacklist) or _contains_blacklisted(kp, blacklist)
    if hit:
        return False, f"blacklisted:{hit}"

    if str(settings.get("privacy_level") or "standard") == "strict":
        if not _has_learning_evidence(evaluation):
            return False, "strict_no_evidence"

    return True, "allowed"


def _has_learning_evidence(evaluation: dict[str, Any]) -> bool:
    evidence = evaluation.get("evidence_for_mastery") or {}
    if isinstance(evidence, dict) and evidence.get("status") in ("passed", "partial"):
        return True
    if (evaluation.get("error_pattern") or "").strip():
        return True
    try:
        if float(evaluation.get("correctness", 0.0) or 0.0) >= 0.5:
            return True
    except (TypeError, ValueError):
        pass
    return False
