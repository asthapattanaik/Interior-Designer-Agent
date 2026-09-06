"""Golden-set shape checks (no agent run)."""

from app.evaluation.cases import load_golden_set


def test_golden_set_has_required_living_room_briefs():
    payload = load_golden_set()
    ids = {case["id"] for case in payload["cases"]}
    assert len(payload["cases"]) >= 25
    for brief_id in ("BR-01", "BR-02", "BR-05", "BR-06", "BR-07", "BR-08", "BR-09", "BR-14"):
        assert brief_id in ids
    kinds = {case["kind"] for case in payload["cases"]}
    assert "normal" in kinds
    assert "adversarial" in kinds
    sources = {case["source"] for case in payload["cases"]}
    assert "database" in sources
    assert "synthetic" in sources
    for case in payload["cases"]:
        assert "input" in case
        assert "expect" in case
        assert case["input"]["style_preference"]
        assert case["input"]["must_haves"]
