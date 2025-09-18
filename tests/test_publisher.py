import base64
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "briefing" / "publisher.py"
spec = importlib.util.spec_from_file_location("briefing.publisher", MODULE_PATH)
publisher = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(publisher)  # type: ignore[attr-defined]


def test_md_to_tg_html_sanitizes_urls():
    md = "# Title\n\n[click me](javascript:alert('x')) and <b>bold</b>"
    html = publisher.md_to_tg_html(md)
    assert "javascript" not in html
    assert "<b>Title</b>" in html


def test_split_html_for_telegram_respects_limit():
    block = ("Paragraph." + "\n\n") * 100
    parts = publisher.split_html_for_telegram(block, limit=500)
    assert parts
    assert all(len(part) <= 500 for part in parts)


def test_telegram_publisher_chunks(monkeypatch):
    calls = []

    class DummyResponse:
        def __init__(self, status_code=200, text="ok"):
            self.status_code = status_code
            self.text = text

    class DummySession:
        def post(self, url, json, timeout):
            calls.append(SimpleNamespace(url=url, payload=json, timeout=timeout))
            return DummyResponse()

    monkeypatch.setattr(publisher, "retry_session", lambda total=3: DummySession())

    cfg = publisher.TelegramConfig(
        chat_id="123",
        bot_token="abc",
        parse_mode="HTML",
        link_preview_disabled=True,
        chunk_limit=600,
        timeout_sec=10.0,
        retries=1,
    )
    pub = publisher.TelegramPublisher(cfg)
    pub.send_markdown("- item\n" * 300)

    assert len(calls) > 1
    for call in calls:
        assert call.payload["chat_id"] == "123"
        assert call.payload["parse_mode"] == "HTML"
        assert call.payload["link_preview_options"] == {"is_disabled": True}
        assert len(call.payload["text"]) <= cfg.chunk_limit


def test_github_artifact_store_upload(monkeypatch, tmp_path):
    get_calls = []
    put_calls = []

    class DummyResponse:
        def __init__(self, status_code, payload=None, text=""):
            self.status_code = status_code
            self._payload = payload or {}
            self.text = text

        def json(self):
            return self._payload

    class DummySession:
        def get(self, url, headers=None, params=None, timeout=None):
            get_calls.append(SimpleNamespace(url=url, headers=headers, params=params, timeout=timeout))
            return DummyResponse(404, {})

        def put(self, url, headers=None, json=None, timeout=None):
            put_calls.append(SimpleNamespace(url=url, headers=headers, json=json, timeout=timeout))
            return DummyResponse(201, {}, text="created")

    monkeypatch.setattr(publisher, "retry_session", lambda total=3: DummySession())

    cfg = publisher.GitHubArtifactStoreConfig(
        repo="org/repo",
        token="token",
        branch="main",
        commit_prefix="briefing",
        committer_name="bot",
        committer_email="bot@example.com",
    )
    store = publisher.GitHubArtifactStore(cfg)

    test_file = tmp_path / "file.md"
    test_file.write_text("hello", encoding="utf-8")

    store.upload(test_file, "2024/09/test/file.md", "briefing: test")

    assert get_calls
    assert put_calls
    payload = put_calls[0].json
    decoded = base64.b64decode(payload["content"]).decode("utf-8")
    assert decoded == "hello"
    assert payload["branch"] == "main"
    assert payload["committer"] == {"name": "bot", "email": "bot@example.com"}


def test_maybe_github_backup_requires_repo_and_token(caplog):
    caplog.set_level("ERROR")
    publisher.maybe_github_backup(["foo.md"], {"github_backup": {"enabled": True}}, "id", "run")
    assert any("missing token or repo" in record.message for record in caplog.records)
PY
