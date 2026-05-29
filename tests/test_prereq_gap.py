import db
from kg_retriever import detect_prereq_gaps, retrieve_kg_context


def _link_prereq(db_sess, sid: str, prereq: str, current: str) -> tuple[db.KGNode, db.KGNode]:
    prereq_node = db.upsert_kg_node(db_sess, sid, "concept", prereq)
    current_node = db.upsert_kg_node(db_sess, sid, "concept", current)
    db.upsert_kg_edge(db_sess, sid, prereq_node.id, current_node.id, "前置于")
    return prereq_node, current_node


def test_detect_prereq_gaps_returns_empty_for_blank_kp(db_sess):
    assert detect_prereq_gaps(db_sess, "s1", "") == []


def test_detect_prereq_gaps_returns_unmastered_prereq(db_sess):
    _link_prereq(db_sess, "s1", "函数单调性", "导数应用")

    assert detect_prereq_gaps(db_sess, "s1", "导数应用") == ["函数单调性"]


def test_detect_prereq_gaps_ignores_mastered_prereq(db_sess):
    _link_prereq(db_sess, "s1", "函数单调性", "导数应用")
    mastery = db.upsert_mastery(
        db_sess,
        "s1",
        "函数单调性",
        correctness=1.0,
        depth=1.0,
        evidence_type="retrieval",
        verification_status="passed",
    )
    mastery.level = 0.82
    mastery.mastery_score = 82.0
    db_sess.flush()

    assert detect_prereq_gaps(db_sess, "s1", "导数应用") == []


def test_retrieve_kg_context_includes_prereq_gap_prompt(db_sess):
    _link_prereq(db_sess, "s1", "函数单调性", "导数应用")

    ctx = retrieve_kg_context(db_sess, "s1", "导数应用")
    text = ctx.format_for_prompt()

    assert ctx.prereq_gaps == ["函数单调性"]
    assert "## 前置缺口" in text
    assert "老师，要学这个我是不是得先搞懂 函数单调性？" in text
