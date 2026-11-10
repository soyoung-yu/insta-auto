"""Runtime settings from .env, with a refreshed token in var/token.json taking priority."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    ig_user_id: str
    ig_access_token: str
    image_base_url: str
    ig_api_version: str
    repo_dir: Path
    var_dir: Path
    out_dir: Path
    account_handle: str = "@hanip.byte"
    # Unified-login system-user tokens work on graph.facebook.com and never expire.
    ig_graph_host: str = "graph.facebook.com"
    ig_token_refresh: bool = False

    @property
    def state_path(self) -> Path:
        return self.var_dir / "state.json"

    @property
    def token_path(self) -> Path:
        return self.var_dir / "token.json"

    @property
    def curriculum_path(self) -> Path:
        return self.repo_dir / "data" / "curriculum.json"


def load_settings(env_file: Path | None = None, *, repo_dir: Path | None = None) -> Settings:
    repo = (repo_dir or Path.cwd()).resolve()
    load_dotenv(env_file or repo / ".env", override=False)
    var_dir = repo / "var"
    token = os.environ.get("IG_ACCESS_TOKEN", "")
    token_file = var_dir / "token.json"
    if token_file.exists():
        token = json.loads(token_file.read_text()).get("access_token", token)
    return Settings(
        ig_user_id=os.environ.get("IG_USER_ID", ""),
        ig_access_token=token,
        image_base_url=os.environ.get("IMAGE_BASE_URL", "").rstrip("/"),
        ig_api_version=os.environ.get("IG_API_VERSION", "v23.0"),
        repo_dir=repo,
        var_dir=var_dir,
        out_dir=repo / "out",
        account_handle=os.environ.get("ACCOUNT_HANDLE", "@hanip.byte"),
        ig_graph_host=os.environ.get("IG_GRAPH_HOST", "graph.facebook.com"),
        ig_token_refresh=os.environ.get("IG_TOKEN_REFRESH", "false").lower() in ("1", "true", "yes"),
    )
