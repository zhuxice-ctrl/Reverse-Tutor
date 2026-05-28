from __future__ import annotations

import engine


def _raw_payload(action_type: str, role: str, *, evidence_type: str = "none") -> dict:
    return {
        "evaluation": {
            "correctness": 0.5,
            "depth": 0.4,
            "entry_status": "has_entry",
            "evidence_for_mastery": {
                "type": evidence_type,
                "status": "passed" if evidence_type != "none" else "none",
                "error_type": "",
                "reason": "test evidence",
            },
            "user_emotion": "frustrated",
            "new_requirements": [],
        },
        "action": {
            "type": action_type,
            "student_role": role,
            "knowledge_point": "当前焦点",
            "difficulty": 0.5,
            "note": "test action",
        },
    }


def test_study_process_summary_uses_study_fields_only():
    evaluation, action, summary = engine._normalize_turn_payload(
        _raw_payload("probe", "probing_student", evidence_type="explanation"),
        user_input="因为这里要先判断条件",
        mode="study",
    )

    assert evaluation and action
    for label in ("当前判断", "使用依据", "本轮策略", "下一步"):
        assert label in summary
    assert "当前任务" not in summary
    assert "感知到的情绪" not in summary


def test_goal_process_summary_uses_goal_fields_only():
    evaluation, action, summary = engine._normalize_turn_payload(
        _raw_payload("advance", "goal_partner"),
        user_input="首页已经改了一半",
        mode="goal",
    )

    assert evaluation and action
    for label in ("当前任务", "阻塞点", "本轮动作", "下一步交付"):
        assert label in summary
    assert "当前判断" not in summary
    assert "感知到的情绪" not in summary


def test_companion_process_summary_uses_companion_fields_only():
    evaluation, action, summary = engine._normalize_turn_payload(
        _raw_payload("empathize", "companion", evidence_type="correction"),
        user_input="今天有点烦",
        mode="companion",
    )

    assert evaluation and action
    for label in ("感知到的情绪", "是否引导", "边界检查"):
        assert label in summary
    assert "当前判断" not in summary
    assert "下一步交付" not in summary
