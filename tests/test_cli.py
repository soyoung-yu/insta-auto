from pathlib import Path

from hanip.__main__ import main
from hanip.curriculum import Topic, save_curriculum
from hanip.state import Pending, State, save_state

TOPICS = [Topic(id="token", title_ko="토큰", keyword_en="token", level=1),
          Topic(id="api", title_ko="API", keyword_en="API", level=1)]


def test_status_shows_number_next_topic_and_pending(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    save_curriculum(TOPICS, tmp_path / "data" / "curriculum.json")
    save_state(State(pending=Pending("2026-11-16", "token", 1, "light", "out/0001")), tmp_path / "var" / "state.json")
    assert main(["status"]) == 0
    out = capsys.readouterr().out
    assert "No.01" in out and "토큰" in out and "승인 대기" in out


def test_curriculum_not_overwritten_without_force(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "data" / "curriculum.json"
    save_curriculum(TOPICS, path)
    before = path.read_text()
    assert main(["curriculum"]) == 1
    assert path.read_text() == before
    assert "--force" in capsys.readouterr().out
