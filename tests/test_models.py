from datetime import datetime
import os
import sys

import pytest

os.environ.setdefault("LOG_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "_logs"))

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from briefing.models import (
    Briefing,
    Bullet,
    BulletDraft,
    ClusterBundle,
    ClusterFacts,
    ClusterItem,
    ClusterSelection,
    DroppedFact,
    Fact,
    FactScores,
    ScoredFact,
    Topic,
    TopicDraft,
)


def test_cluster_and_briefing_models_roundtrip():
    item = ClusterItem(
        item_id="hn-1",
        title="Example post",
        snippet="New release improves latency.",
        url="https://example.com/post",
        source="hackernews",
    )
    bundle = ClusterBundle(
        cluster_id="hn-001",
        items=[item],
        canonical_links=["https://example.com/post"],
        language="zh",
    )

    fact = Fact(fact_id="fact-0", text="v2.0 降低 30% 延迟", url="https://example.com/release")
    facts = ClusterFacts(cluster_id=bundle.cluster_id, facts=[fact])

    scores = FactScores(actionability=2, novelty=1, impact=2, reusability=1, reliability=1, agentic_bonus=1)
    picked = ScoredFact(
        fact_id=fact.fact_id,
        text=fact.text,
        url=fact.url,
        scores=scores,
        strategic_flag=False,
        rationale="提供明确配置步骤",
    )
    selection = ClusterSelection(
        cluster_id=facts.cluster_id,
        picked=[picked],
        dropped=[DroppedFact(fact_id="fact-1", reason="重复")],
    )

    bullet_draft = BulletDraft(text="更新发布 → 启用新 flag → 临时仅限企业计划", url=fact.url, fact_ids=[fact.fact_id])
    topic_draft = TopicDraft(
        topic_id="cluster-hn-001",
        headline="新版本降低延迟，适合延伸 agentic 工作流",
        bullets=[bullet_draft],
        annotations={"agentic": True},
    )

    bullet = Bullet(text=bullet_draft.text, url=bullet_draft.url)
    topic = Topic(topic_id=topic_draft.topic_id, headline=topic_draft.headline, bullets=[bullet])

    briefing = Briefing(title="Daily Engineering Brief", date=datetime.utcnow(), topics=[topic])

    assert bundle.cluster_id == facts.cluster_id == selection.cluster_id
    assert selection.has_agentic()
    assert selection.max_score() == scores.weighted_total
    assert briefing.topics[0].bullets[0].url == fact.url


def test_topic_draft_bullet_limit():
    with pytest.raises(ValueError):
        TopicDraft(
            topic_id="cluster-test",
            headline="Too many bullets",
            bullets=[
                BulletDraft(text=f"bullet {i}", url="https://example.com", fact_ids=["fact-0"]) for i in range(5)
            ],
        )
