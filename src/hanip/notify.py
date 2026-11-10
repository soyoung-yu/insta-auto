"""macOS notification and opening files for the human-approval runs."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def notify(title: str, message: str) -> None:
    script = f"display notification {json.dumps(message)} with title {json.dumps(title)}"
    subprocess.run(["osascript", "-e", script], check=False)


def open_file(path: Path) -> None:
    subprocess.run(["open", str(path)], check=False)
