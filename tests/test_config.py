import json

from hanip.config import load_settings


def _env(tmp_path, extra=""):
    env = tmp_path / ".env"
    env.write_text(
        "IG_USER_ID=123\nIG_ACCESS_TOKEN=a\nIMAGE_BASE_URL=https://raw.example/repo/main/\n" + extra
    )
    return env


def test_reads_env_file(tmp_path, monkeypatch):
    for k in ("IG_USER_ID", "IG_ACCESS_TOKEN", "IMAGE_BASE_URL", "IG_API_VERSION"):
        monkeypatch.delenv(k, raising=False)
    s = load_settings(_env(tmp_path), repo_dir=tmp_path)
    assert s.ig_user_id == "123"
    assert s.ig_access_token == "a"
    assert s.image_base_url == "https://raw.example/repo/main"  # trailing slash stripped
    assert s.ig_api_version == "v23.0"
    assert s.account_handle == "@hanip.byte"
    assert s.var_dir == tmp_path / "var"


def test_token_file_overrides_env(tmp_path, monkeypatch):
    for k in ("IG_USER_ID", "IG_ACCESS_TOKEN", "IMAGE_BASE_URL"):
        monkeypatch.delenv(k, raising=False)
    (tmp_path / "var").mkdir()
    (tmp_path / "var" / "token.json").write_text(json.dumps({"access_token": "b"}))
    assert load_settings(_env(tmp_path), repo_dir=tmp_path).ig_access_token == "b"
