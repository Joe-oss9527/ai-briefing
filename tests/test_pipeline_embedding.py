import os
from pathlib import Path

import pytest

_TEST_LOG_DIR = Path(__file__).resolve().parent / "_logs"
os.environ.setdefault("LOG_DIR", str(_TEST_LOG_DIR))
_TEST_LOG_DIR.mkdir(parents=True, exist_ok=True)

import briefing.pipeline as pipeline


def test_embed_texts_respects_batch_limits(monkeypatch, tmp_path):
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "logs"))

    batches = []

    def fake_post(url, json=None, timeout=None):
        assert url.endswith("/embeddings")
        payload = json["input"]
        batches.append(payload)

        class _Resp:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                # Return embeddings encoding the character length so we can verify order
                return {
                    "data": [
                        {"embedding": [float(len(text)), float(index)]}
                        for index, text in enumerate(payload)
                    ]
                }

        return _Resp()

    monkeypatch.setattr(pipeline.requests, "post", fake_post)

    texts = ["a" * 400, "b" * 400, "c" * 120]

    embeddings = pipeline._embed_texts(
        texts,
        max_batch_tokens=100,
        max_item_chars=240,
        chars_per_token=2.0,
    )

    assert embeddings.shape == (3, 2)
    # each original text should be truncated to 200 characters (min(240, 100*2))
    assert embeddings[0][0] == pytest.approx(200.0)
    assert embeddings[1][0] == pytest.approx(200.0)
    assert embeddings[2][0] == pytest.approx(120.0)

    # dynamic batching should have produced three separate requests due to the token limit
    assert len(batches) == 3
    assert all(len(batch) == 1 for batch in batches[:-1])
    assert all(len(text) <= 200 for batch in batches for text in batch)


def test_embed_texts_handles_413(monkeypatch, tmp_path):
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "logs_413"))

    call_payloads = []

    def fake_post(url, json=None, timeout=None):
        payload = json["input"]
        call_payloads.append([len(text) for text in payload])

        class _Resp:
            def __init__(self, status_code: int, data: list[float] | None = None):
                self.status_code = status_code
                self._data = data or []

            def raise_for_status(self):
                if self.status_code >= 400 and self.status_code != 413:
                    import requests

                    raise requests.exceptions.HTTPError(response=self)
                return None

            def json(self):
                if self.status_code != 200:
                    return {}
                return {"data": [{"embedding": [float(val)]} for val in self._data]}

        if len(payload) > 1:
            return _Resp(413)

        length = len(payload[0])
        if length > 120:
            return _Resp(413)

        data = [float(length)]
        return _Resp(200, data)

    monkeypatch.setattr(pipeline.requests, "post", fake_post)

    texts = ["a" * 280, "b" * 280]

    embeddings = pipeline._embed_texts(
        texts,
        max_batch_tokens=150,
        max_item_chars=400,
        chars_per_token=4.0,
    )

    assert embeddings.shape == (2, 1)
    assert embeddings[0][0] <= 120.0
    assert embeddings[1][0] <= 120.0
    # Ensure we attempted a combined batch first, then singles with progressively shorter payloads
    assert call_payloads[0] == [280, 280]
    assert all(len(payload) == 1 for payload in call_payloads[1:])
