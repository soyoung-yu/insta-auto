"""macOS notification and opening files for the human-approval runs."""

from __future__ import annotations

import subprocess
from pathlib import Path


def _applescript_string(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def notify(title: str, message: str) -> None:
    script = f"display notification {_applescript_string(message)} with title {_applescript_string(title)}"
    subprocess.run(["osascript", "-e", script], check=False)


def open_file(path: Path) -> None:
    subprocess.run(["open", str(path)], check=False)
