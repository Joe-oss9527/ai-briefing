import json
import os
import sys
from collections import deque
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("LOG_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "_logs"))

from briefing.pipeline_multistep import compute_metrics, run_multistage_pipeline


@pytest.fixture(name="sample_bundles")
def fixture_sample_bundles() -> list[dict]:
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "sample_bundles.json"
    with fixture_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def test_run_multistage_pipeline_with_mocked_llm(monkeypatch, tmp_path, sample_bundles):
    responses = deque(
        [
            {
                "cluster_id": "cluster-hn-001",
                "facts": [
                    {
                        "fact_id": "fact-0",
                        "text": "Acme CLI 2.0 adds streaming tailing",
                        "url": "https://example.com/acme-cli",
                    }
                ],
                "rejected": [],
            },
            {
                "cluster_id": "cluster-hn-001",
                "picked": [
                    {
                        "fact_id": "fact-0",
                        "text": "Acme CLI 2.0 adds streaming tailing",
                        "url": "https://example.com/acme-cli",
                        "scores": {
                            "actionability": 3,
                            "novelty": 1,
                            "impact": 2,
                            "reusability": 1,
                            "reliability": 1,
                            "agentic_bonus": 0,
                        },
                        "strategic_flag": False,
                        "rationale": "Ready-to-use CLI upgrade",
                    }
                ],
                "dropped": [],
            },
            {
                "topic_id": "cluster-hn-001",
                "headline": "Acme CLI 降低调试开销",
                "bullets": [
                    {
                        "text": "Acme CLI 2.0 引入实时 tail → 立刻监控部署 → 需启用 beta 标志",
                        "url": "https://example.com/acme-cli",
                        "fact_ids": ["fact-0"],
                    }
                ],
                "annotations": {},
            },
            {
                "cluster_id": "cluster-tw-002",
                "facts": [
                    {
                        "fact_id": "fact-0",
                        "text": "Cursor 支持离线运行 Jest 并给提示",
                        "url": "https://twitter.com/cursor/status/456",
                    }
                ],
                "rejected": [],
            },
            {
                "cluster_id": "cluster-tw-002",
                "picked": [
                    {
                        "fact_id": "fact-0",
                        "text": "Cursor 支持离线运行 Jest 并给提示",
                        "url": "https://twitter.com/cursor/status/456",
                        "scores": {
                            "actionability": 2,
                            "novelty": 2,
                            "impact": 2,
                            "reusability": 2,
                            "reliability": 1,
                            "agentic_bonus": 1,
                        },
                        "strategic_flag": False,
                        "rationale": "提升代理式测试效率",
                    }
                ],
                "dropped": [],
            },
            {
                "topic_id": "cluster-tw-002",
                "headline": "Cursor 离线测试升级",
                "bullets": [
                    {
                        "text": "Cursor 新增离线 Jest 运行 → 可在 CI 断网时保留提示 → 目前仅限团队版",
                        "url": "https://twitter.com/cursor/status/456",
                        "fact_ids": ["fact-0"],
                    }
                ],
                "annotations": {"agentic": True},
            },
        ]
    )

    def fake_call_with_schema(**_kwargs):
        if not responses:
            raise AssertionError("No more mocked responses available")
        return responses.popleft()

    monkeypatch.setattr("briefing.pipeline_multistep.call_with_schema", fake_call_with_schema)

    config = {
        "briefing_title": "Daily AI Brief",
        "processing": {"multi_stage": True},
        "output": {"dir": str(tmp_path / "out")},
        "rendering": {},
    }

    briefing, state = run_multistage_pipeline(
        sample_bundles,
        config,
        briefing_id="test-brief",
        output_root=tmp_path,
    )

    assert briefing.title == "Daily AI Brief"
    assert len(briefing.topics) == 2
    assert "cluster-hn-001" in state.topics
    assert "cluster-tw-002" in state.topics
    assert state.artifact_root is not None
    stage_dir = state.artifact_root / "cluster-hn-001"
    assert (stage_dir / "cluster-hn-001_stage1.json").exists()
    assert (state.artifact_root / "stage4_briefing.json").exists()

    assert briefing.topics[0].headline == "Agentic Focus"
    assert len(briefing.topics[0].bullets) == 1
    assert briefing.topics[1].headline == "Acme CLI 降低调试开销"
    for topic in briefing.topics:
        assert 1 <= len(topic.bullets) <= 4
        urls = {str(bullet.url) for bullet in topic.bullets}
        assert len(urls) == len(topic.bullets)
        for bullet in topic.bullets:
            assert str(bullet.url).startswith("https://")

    metrics = compute_metrics(state, briefing, config)
    assert metrics["facts_picked"] == 2
    assert metrics["avg_actionability"] > 0


def test_invalid_item_urls_do_not_drop_cluster(monkeypatch, tmp_path):
    # Bundle contains one invalid-URL item and one valid-URL item
    input_bundles = [
        {
            "topic_id": "cluster-mix-001",
            "items": [
                {
                    "id": "bad-1",
                    "text": "Some text",
                    "url": "",  # invalid
                    "timestamp": "2024-09-01T12:00:00Z",
                    "metadata": {"source": "rss"},
                },
                {
                    "id": "ok-2",
                    "text": "Valid item",
                    "url": "https://valid.example.com/ok",
                    "timestamp": "2024-09-01T12:00:00Z",
                    "metadata": {"source": "rss"},
                },
            ],
        }
    ]

    # Mock LLM calls for stages 1-3
    def fake_call_with_schema(**kwargs):
        schema = kwargs.get("schema", {})
        # Stage 1
        if schema.get("title") == "ClusterFacts":
            return {
                "cluster_id": "cluster-mix-001",
                "facts": [
                    {
                        "fact_id": "f1",
                        "text": "Valid fact",
                        "url": "https://valid.example.com/ok",
                    }
                ],
                "rejected": [],
            }
        # Stage 2
        if schema.get("title") == "ClusterSelection":
            return {
                "cluster_id": "cluster-mix-001",
                "picked": [
                    {
                        "fact_id": "f1",
                        "text": "Valid fact",
                        "url": "https://valid.example.com/ok",
                        "scores": {
                            "actionability": 2,
                            "novelty": 1,
                            "impact": 1,
                            "reusability": 1,
                            "reliability": 1,
                            "agentic_bonus": 0,
                        },
                        "strategic_flag": False,
                        "rationale": "ok",
                    }
                ],
                "dropped": [],
            }
        # Stage 3
        if schema.get("title") == "TopicDraft":
            return {
                "topic_id": "cluster-mix-001",
                "headline": "Mixed Cluster Survives",
                "bullets": [
                    {
                        "text": "Bullet based on valid item",
                        "url": "https://valid.example.com/ok",
                        "fact_ids": ["f1"],
                    }
                ],
                "annotations": {},
            }
        raise AssertionError("Unexpected schema call")

    monkeypatch.setattr("briefing.pipeline_multistep.call_with_schema", fake_call_with_schema)

    config = {
        "briefing_title": "Daily AI Brief",
        "processing": {"multi_stage": True},
        "output": {"dir": str(tmp_path / "out")},
        "rendering": {},
    }

    briefing, state = run_multistage_pipeline(
        input_bundles,
        config,
        briefing_id="test-brief-mix",
        output_root=tmp_path,
    )

    # Cluster should not be dropped; invalid item filtered, valid item kept
    assert len(briefing.topics) == 1
    assert briefing.topics[0].headline == "Mixed Cluster Survives"
    assert len(briefing.topics[0].bullets) == 1
    assert str(briefing.topics[0].bullets[0].url).startswith("https://")
