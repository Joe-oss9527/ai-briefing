import os
import types
from typing import Any, Dict

import pytest

# Ensure logger writes to a temp folder within tests
os.environ.setdefault("LOG_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "_logs"))


def _fake_response(payload: Dict[str, Any]):
    class R:
        status_code = 200

        def json(self):
            return payload

        def raise_for_status(self):
            return None

    return R()


def test_rss_adapter_uses_links_alternate(monkeypatch):
    from briefing.sources import rss_adapter

    class FakeFeed:
        def __init__(self):
            self.entries = [
                {
                    "title": "Hello",
                    "links": [{"rel": "alternate", "href": "example.com/post"}],
                    "published": "2024-09-01T12:00:00Z",
                }
            ]

    monkeypatch.setattr(rss_adapter.feedparser, "parse", lambda url: FakeFeed())

    out = rss_adapter.fetch({"urls": ["http://dummy"]})
    assert len(out) == 1
    assert out[0]["url"].startswith("https://")
    assert out[0]["url"] == "https://example.com/post"


def test_rss_adapter_uses_origlink(monkeypatch):
    from briefing.sources import rss_adapter

    class FakeFeed:
        def __init__(self):
            self.entries = [
                {
                    "title": "Hello2",
                    "feedburner_origlink": "http://site.example.org/a",
                    "date_published": "2024-09-01T12:00:00Z",
                }
            ]

    monkeypatch.setattr(rss_adapter.feedparser, "parse", lambda url: FakeFeed())

    out = rss_adapter.fetch({"urls": ["http://dummy"]})
    assert len(out) == 1
    assert out[0]["url"] == "http://site.example.org/a"


def test_rss_adapter_uses_id_when_urlish(monkeypatch):
    from briefing.sources import rss_adapter

    class FakeFeed:
        def __init__(self):
            self.entries = [
                {
                    "id": "https://blog.example.com/entry",
                    "summary": "hi",
                    "updated": "2024-09-01T12:00:00Z",
                }
            ]

    monkeypatch.setattr(rss_adapter.feedparser, "parse", lambda url: FakeFeed())

    out = rss_adapter.fetch({"urls": ["http://dummy"]})
    assert len(out) == 1
    assert out[0]["url"] == "https://blog.example.com/entry"


def test_twitter_list_adapter_fallback_to_link(monkeypatch):
    from briefing.sources import twitter_list_adapter

    payload = {
        "items": [
            {
                "id": "tw1",
                "link": "twitter.com/user/status/123",
                "description": "hello",
                "date_published": "2024-09-01T12:00:00Z",
            }
        ]
    }

    monkeypatch.setattr(
        twitter_list_adapter.requests,
        "get",
        lambda url, timeout=30: _fake_response(payload),
    )

    out = twitter_list_adapter.fetch({"id": "list1"})
    assert len(out) == 1
    assert out[0]["url"] == "https://twitter.com/user/status/123"


def test_twitter_list_adapter_drops_invalid_url(monkeypatch):
    from briefing.sources import twitter_list_adapter

    payload = {
        "items": [
            {
                "id": "tw2",
                "description": "hello",
                "date": "2024-09-01T12:00:00Z",
                # no url/link -> should be dropped
            }
        ]
    }

    monkeypatch.setattr(
        twitter_list_adapter.requests,
        "get",
        lambda url, timeout=30: _fake_response(payload),
    )

    out = twitter_list_adapter.fetch({"id": "list1"})
    assert len(out) == 0
