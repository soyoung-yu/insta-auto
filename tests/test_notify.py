import subprocess

import hanip.notify as notify_mod


def test_notification_script_keeps_korean_and_escapes_quotes(monkeypatch):
    seen = []
    monkeypatch.setattr(notify_mod.subprocess, "run", lambda args, **k: seen.append(args) or subprocess.CompletedProcess(args, 0))
    notify_mod.notify("오늘의 한입", 'No.01 "승인" 대기 \\ 확인')
    script = seen[0][2]
    assert "오늘의 한입" in script and "\\u" not in script
    assert script == 'display notification "No.01 \\"승인\\" 대기 \\\\ 확인" with title "오늘의 한입"'
