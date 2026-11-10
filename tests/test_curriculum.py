import pytest

from hanip.claude_cli import ClaudeError
from hanip.curriculum import Topic, generate_curriculum, load_curriculum, save_curriculum

ITEM = {"id": "token", "title_ko": "토큰", "keyword_en": "token", "level": 1}


def test_generate_curriculum_rejects_duplicate_ids():
    with pytest.raises(ClaudeError):
        generate_curriculum(2, run=lambda p: [ITEM, ITEM])


def test_generate_curriculum_passes_count_in_prompt():
    seen = {}

    def run(p):
        seen["p"] = p
        return [ITEM, {**ITEM, "id": "api", "title_ko": "API", "keyword_en": "API"}]

    topics = generate_curriculum(2, run=run)
    assert [t.id for t in topics] == ["token", "api"]
    assert "2" in seen["p"]


def test_save_and_load_roundtrip(tmp_path):
    topics = [Topic(**ITEM)]
    save_curriculum(topics, tmp_path / "data" / "curriculum.json")
    assert load_curriculum(tmp_path / "data" / "curriculum.json") == topics


def test_invalid_shape_raises_claude_error():
    with pytest.raises(ClaudeError):
        generate_curriculum(1, run=lambda p: [{"id": "x"}])
