"""Call Claude Code in print mode (`claude -p`) and parse a JSON answer.

Uses the user's Claude Code subscription on this Mac; no API key.
"""

from __future__ import annotations

import json
import re
import subprocess
from typing import Any

FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


class ClaudeError(Exception):
    pass


def run_claude_json(prompt: str, *, runner=subprocess.run, timeout: int = 600) -> Any:
    args = ["claude", "-p", prompt, "--output-format", "json"]
    try:
        proc = runner(args, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise ClaudeError(f"claude 실행 실패: {e}") from e
    if proc.returncode != 0:
        raise ClaudeError(f"claude 종료 코드 {proc.returncode}: {proc.stderr[-500:]}")
    try:
        envelope = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise ClaudeError(f"claude 출력이 JSON이 아님: {proc.stdout[:300]}") from e
    if envelope.get("is_error"):
        raise ClaudeError(f"claude 오류: {envelope.get('result')}")
    text = envelope.get("result", "")
    m = FENCE.search(text)
    if m:
        text = m.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ClaudeError(f"답변이 JSON이 아님: {text[:300]}") from e
