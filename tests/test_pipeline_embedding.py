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
