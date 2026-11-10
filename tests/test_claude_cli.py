import json
import subprocess

import pytest

from hanip.claude_cli import ClaudeError, run_claude_json


def fake_runner(stdout, code=0, seen=None):
    def run(args, **kwargs):
        if seen is not None:
            seen.append(args)
        return subprocess.CompletedProcess(args, code, stdout=stdout, stderr="boom")

    return run


def test_parses_fenced_json():
    out = json.dumps({"result": '```json\n{"a": 1}\n```', "is_error": False})
    assert run_claude_json("x", runner=fake_runner(out)) == {"a": 1}


def test_parses_plain_json():
    out = json.dumps({"result": '[1, 2]', "is_error": False})
    assert run_claude_json("x", runner=fake_runner(out)) == [1, 2]


def test_calls_claude_print_mode_with_json_output():
    seen = []
    run_claude_json("hello", runner=fake_runner(json.dumps({"result": "{}"}), seen=seen))
    assert seen[0][:3] == ["claude", "-p", "hello"]
    assert "--output-format" in seen[0] and "json" in seen[0]


def test_invalid_json_raises_claude_error():
    out = json.dumps({"result": "죄송해요", "is_error": False})
    with pytest.raises(ClaudeError):
        run_claude_json("x", runner=fake_runner(out))


def test_is_error_raises():
    out = json.dumps({"result": "{}", "is_error": True})
    with pytest.raises(ClaudeError):
        run_claude_json("x", runner=fake_runner(out))


def test_nonzero_exit_raises():
    with pytest.raises(ClaudeError):
        run_claude_json("x", runner=fake_runner("", code=1))
