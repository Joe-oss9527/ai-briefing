"""Pydantic models shared across the multi-stage briefing pipeline."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, HttpUrl, field_validator


class BaseModelWithConfig(BaseModel):
    """Base model enabling alias generation and forbidding silent data loss."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class ClusterItem(BaseModelWithConfig):
    """Single raw item grouped into a cluster before LLM processing."""

    item_id: Optional[str] = Field(
        default=None,
        description="Source-specific identifier",
        validation_alias=AliasChoices("item_id", "id"),
    )
    title: Optional[str] = None
    snippet: Optional[str] = None
    text: Optional[str] = None
    url: HttpUrl
    source: Optional[str] = Field(default=None, description="Channel name, e.g. hn/twitter/reddit")
    author: Optional[str] = None
    timestamp: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class ClusterBundle(BaseModelWithConfig):
    """Bundle forwarded to Stage 1 for fact extraction."""

    cluster_id: str = Field(validation_alias=AliasChoices("cluster_id", "topic_id"))
    items: List[ClusterItem] = Field(default_factory=list)
    canonical_links: List[HttpUrl] = Field(default_factory=list)
    language: Optional[str] = None
    summary: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class Fact(BaseModelWithConfig):
    fact_id: str
    text: str
    url: HttpUrl


class RejectedFact(BaseModelWithConfig):
    fact_id: Optional[str] = None
    item_id: Optional[str] = None
    reason: str


class ClusterFacts(BaseModelWithConfig):
    cluster_id: str
    facts: List[Fact] = Field(default_factory=list)
    rejected: List[RejectedFact] = Field(default_factory=list)


class FactScores(BaseModelWithConfig):
    actionability: int = Field(ge=0, le=3)
    novelty: int = Field(ge=0, le=2)
    impact: int = Field(ge=0, le=2)
    reusability: int = Field(ge=0, le=2)
    reliability: int = Field(ge=0, le=1)
    agentic_bonus: int = Field(default=0, ge=0, le=1)

    @property
    def weighted_total(self) -> int:
        return (
            self.actionability
            + self.novelty
            + self.impact
            + self.reusability
            + self.reliability
            + self.agentic_bonus
        )


class ScoredFact(BaseModelWithConfig):
    fact_id: str
    text: str
    url: HttpUrl
    scores: FactScores
    strategic_flag: bool = False
    rationale: str


class DroppedFact(BaseModelWithConfig):
    fact_id: str
    reason: str


class ClusterSelection(BaseModelWithConfig):
    cluster_id: str
    picked: List[ScoredFact] = Field(default_factory=list)
    dropped: List[DroppedFact] = Field(default_factory=list)
    notes: Optional[str] = None

    def max_score(self) -> int:
        if not self.picked:
            return 0
        return max(f.scores.weighted_total for f in self.picked)

    def has_agentic(self) -> bool:
        return any(f.scores.agentic_bonus > 0 for f in self.picked)

    def has_strategic(self) -> bool:
        return any(f.strategic_flag for f in self.picked)


class BulletDraft(BaseModelWithConfig):
    text: str
    url: HttpUrl
    fact_ids: List[str] = Field(default_factory=list)


class TopicDraft(BaseModelWithConfig):
    topic_id: str
    headline: str
    bullets: List[BulletDraft] = Field(default_factory=list)
    annotations: Dict[str, bool] = Field(default_factory=dict)
    notes: Optional[str] = None

    @field_validator("bullets")
    @classmethod
    def validate_bullet_count(cls, bullets: List[BulletDraft]) -> List[BulletDraft]:
        if bullets and len(bullets) > 4:
            raise ValueError("bullets cannot exceed 4 entries")
        return bullets


class Bullet(BaseModelWithConfig):
    text: str
    url: HttpUrl


class Topic(BaseModelWithConfig):
    topic_id: str
    headline: str
    bullets: List[Bullet] = Field(default_factory=list)


class Briefing(BaseModelWithConfig):
    title: str
    date: datetime
    topics: List[Topic] = Field(default_factory=list)

    @field_validator("topics")
    @classmethod
    def validate_topics(cls, topics: List[Topic]) -> List[Topic]:
        for topic in topics:
            if not 1 <= len(topic.bullets) <= 4:
                raise ValueError("each topic must include 1-4 bullets")
        return topics
