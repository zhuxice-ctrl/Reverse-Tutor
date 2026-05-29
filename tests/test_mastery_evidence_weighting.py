from __future__ import annotations

import db


def _session(db_sess, sid: str = "mastery-evidence") -> str:
    db_sess.add(db.Session(id=sid, title="t", persona_json="{}", plan_json="[]"))
    db_sess.commit()
    return sid


def test_verification_status_none_does_not_increase_existing_score(db_sess):
    sid = _session(db_sess)
    m = db.upsert_mastery(
        db_sess,
        sid,
        "单调性",
        correctness=1.0,
        depth=1.0,
        evidence_type="delayed_retrieval",
        verification_status="passed",
    )
    before = m.mastery_score

    m = db.upsert_mastery(
        db_sess,
        sid,
        "单调性",
        correctness=1.0,
        depth=1.0,
        evidence_type="none",
        verification_status="none",
    )

    assert m.mastery_score == before
    assert m.last_evidence_type == "none"
    assert m.last_verification_status == "none"
    assert m.attempts == 2


def test_repeated_explanation_cannot_reach_mastered_band(db_sess):
    sid = _session(db_sess)

    for _ in range(12):
        m = db.upsert_mastery(
            db_sess,
            sid,
            "判别式",
            correctness=1.0,
            depth=1.0,
            evidence_type="explanation",
            verification_status="passed",
        )

    assert m.mastery_score < 50.0
    assert db.mastery_band(m.mastery_score) != "可迁移纠错"


def test_stronger_evidence_lifts_more_than_explanation(db_sess):
    sid = _session(db_sess)

    explanation = db.upsert_mastery(
        db_sess,
        sid,
        "解释证据",
        correctness=1.0,
        depth=1.0,
        evidence_type="explanation",
        verification_status="passed",
    )
    delayed = db.upsert_mastery(
        db_sess,
        sid,
        "延迟提取证据",
        correctness=1.0,
        depth=1.0,
        evidence_type="delayed_retrieval",
        verification_status="passed",
    )
    correction = db.upsert_mastery(
        db_sess,
        sid,
        "纠错证据",
        correctness=1.0,
        depth=1.0,
        evidence_type="correction",
        verification_status="passed",
    )

    assert delayed.mastery_score > explanation.mastery_score
    assert correction.mastery_score > delayed.mastery_score


def test_failed_verification_rolls_back_high_score(db_sess):
    sid = _session(db_sess)
    m = db.upsert_mastery(
        db_sess,
        sid,
        "函数图像",
        correctness=1.0,
        depth=1.0,
        evidence_type="correction",
        verification_status="passed",
    )
    m = db.upsert_mastery(
        db_sess,
        sid,
        "函数图像",
        correctness=1.0,
        depth=1.0,
        evidence_type="correction",
        verification_status="passed",
    )
    before = m.mastery_score

    m = db.upsert_mastery(
        db_sess,
        sid,
        "函数图像",
        correctness=0.0,
        depth=0.0,
        evidence_type="correction",
        verification_status="failed",
    )

    assert before > 50.0
    assert m.mastery_score == round(before - 8.0, 2)
    assert m.review_interval == 1
