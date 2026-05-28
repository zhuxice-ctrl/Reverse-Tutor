from __future__ import annotations

import db
import engine
import kg_gate


def _session(db_sess, sid: str = "kg-gate", *, settings=None) -> db.Session:
    s = engine.create_session(
        db_sess,
        title="",
        role="student",
        goal="local test",
        settings=settings or {},
    )
    s.id = sid
    db_sess.commit()
    return s


def _evaluation(*, correctness=0.4, evidence=None, error_pattern="", entry="has_entry"):
    return {
        "entry_status": entry,
        "correctness": correctness,
        "depth": 0.4,
        "error_pattern": error_pattern,
        "evidence_for_mastery": evidence or {"type": "none", "status": "none"},
    }


def _action(kp="Chain rule", action_type="probe"):
    return {"type": action_type, "knowledge_point": kp}


def _payload(*, kp="Chain rule"):
    return {
        "evaluation": {
            "correctness": 0.7,
            "depth": 0.5,
            "entry_status": "has_entry",
            "error_pattern": "",
            "evidence_for_mastery": {
                "type": "explanation",
                "status": "passed",
                "error_type": "",
                "reason": "gate test",
            },
            "user_emotion": "neutral",
            "new_requirements": [],
        },
        "action": {
            "type": "probe",
            "student_role": "probing_student",
            "knowledge_point": kp,
            "difficulty": 0.5,
            "note": "gate test",
        },
        "reply": "mock reply",
        "anchor_updates": [],
        "cited_chunk_ids": [],
    }


def _make_sequence_mock(payloads: list[dict]):
    it = iter(payloads)

    async def mock_chat_json(system, messages, **kwargs):
        return next(it)

    return mock_chat_json


def test_should_extract_allows_default_learning_turn():
    assert kg_gate.should_extract({}, "I can explain it now", _evaluation(), _action()) == (True, "allowed")


def test_should_extract_blocks_when_disabled():
    assert kg_gate.should_extract(
        {"kg_extraction_enabled": False},
        "I can explain it now",
        _evaluation(),
        _action(),
    ) == (False, "disabled")


def test_should_extract_blocks_empty_knowledge_point():
    assert kg_gate.should_extract({}, "I can explain it now", _evaluation(), _action(kp="")) == (False, "no_kp")


def test_should_extract_blocks_default_blacklist_in_user_input():
    allowed, reason = kg_gate.should_extract({}, "我的手机号是 13800000000", _evaluation(), _action())

    assert allowed is False
    assert reason.startswith("blacklisted:")


def test_should_extract_blocks_user_defined_blacklist_in_user_input():
    allowed, reason = kg_gate.should_extract(
        {"kg_blacklist": ["秘密项目"]},
        "这里包含秘密项目内容",
        _evaluation(),
        _action(),
    )

    assert allowed is False
    assert reason == "blacklisted:秘密项目"


def test_should_extract_blocks_blacklist_inside_knowledge_point():
    allowed, reason = kg_gate.should_extract({}, "normal learning answer", _evaluation(), _action(kp="身份证验证"))

    assert allowed is False
    assert reason.startswith("blacklisted:")


def test_should_extract_blocks_strict_privacy_without_learning_evidence():
    assert kg_gate.should_extract(
        {"privacy_level": "strict"},
        "normal learning answer",
        _evaluation(correctness=0.1, evidence={"type": "none", "status": "none"}, error_pattern=""),
        _action(),
    ) == (False, "strict_no_evidence")


def test_should_extract_allows_strict_privacy_with_error_pattern():
    assert kg_gate.should_extract(
        {"privacy_level": "strict"},
        "normal learning answer",
        _evaluation(correctness=0.1, error_pattern="sign error"),
        _action(),
    ) == (True, "allowed")


def test_should_extract_allows_strict_privacy_with_passed_evidence():
    assert kg_gate.should_extract(
        {"privacy_level": "strict"},
        "normal learning answer",
        _evaluation(correctness=0.1, evidence={"type": "explanation", "status": "passed"}),
        _action(),
    ) == (True, "allowed")


def test_has_learning_evidence_true_when_correctness_at_least_half():
    assert kg_gate._has_learning_evidence(_evaluation(correctness=0.5)) is True


async def test_run_turn_default_session_extracts_kg_nodes(db_sess, monkeypatch):
    s = _session(db_sess, "kg-gate-default")
    monkeypatch.setattr(engine.llm, "chat_json", _make_sequence_mock([_payload()]))

    await engine.run_turn(db_sess, s.id, "I used the derivative rule")

    assert db.list_kg_nodes(db_sess, s.id)


async def test_run_turn_disabled_session_skips_kg_extraction(db_sess, monkeypatch):
    s = _session(db_sess, "kg-gate-disabled", settings={"kg_extraction_enabled": False})
    monkeypatch.setattr(engine.llm, "chat_json", _make_sequence_mock([_payload()]))

    await engine.run_turn(db_sess, s.id, "I used the derivative rule")

    assert db.list_kg_nodes(db_sess, s.id) == []


async def test_run_turn_blacklisted_user_input_skips_kg_extraction(db_sess, monkeypatch):
    s = _session(db_sess, "kg-gate-blacklisted")
    monkeypatch.setattr(engine.llm, "chat_json", _make_sequence_mock([_payload()]))

    await engine.run_turn(db_sess, s.id, "我的手机号是 13800000000")

    assert db.list_kg_nodes(db_sess, s.id) == []
