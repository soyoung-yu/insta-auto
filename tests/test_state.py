from hanip.state import (
    HistoryEntry,
    Pending,
    State,
    already_published_on,
    load_state,
    needs_approval,
    next_number,
    save_state,
    theme_for,
)


def test_theme_alternates_by_number():
    assert theme_for(1) == "light"
    assert theme_for(2) == "dark"
    assert theme_for(13) == "light"


def test_needs_approval_first_five_only():
    assert [needs_approval(n) for n in (1, 5, 6)] == [True, True, False]


def test_next_number_is_published_count_plus_one():
    assert next_number(State(published_count=4)) == 5


def test_roundtrip_with_pending_and_history(tmp_path):
    s = State(
        published_count=2,
        curriculum_index=2,
        history=[HistoryEntry(1, "2026-11-10", "token", "light", "m1")],
        pending=Pending("2026-11-11", "api", 3, "light", "out/0003"),
        token_refreshed_at="2026-11-01",
    )
    save_state(s, tmp_path / "state.json")
    assert load_state(tmp_path / "state.json") == s


def test_missing_file_gives_default(tmp_path):
    assert load_state(tmp_path / "nope.json") == State()


def test_already_published_on():
    s = State(history=[HistoryEntry(1, "2026-11-11", "token", "light", "m1")])
    assert already_published_on(s, "2026-11-11")
    assert not already_published_on(s, "2026-11-12")
