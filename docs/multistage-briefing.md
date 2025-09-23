# Multi-Stage Briefing Pipeline Plan

Status: draft v0.1
Owner: briefing team
Last updated: 2025-09-22

## Objectives
- Increase reliability and actionability using a multi-stage LLM pipeline.
- Keep JSON-only contract; reduce hallucinations; improve dedup/ordering; add observability.
- Tone down hard “Agentic-only” bias to a tie-breaker + optional section.

## Scope
- Sources: HN, Twitter/X, Reddit (extensible).
- Outputs: final JSON schema unchanged (title, date, topics[headline, bullets[text,url]]).
- Non-goals: UI changes, new external integrations.

## Architecture Overview
Stages (extract → score → compose → format/QC), with cached artifacts per stage under `out/<briefing_id>/stages/`.

1) Stage 0: Ingest + Cluster
   - Normalize items; dedup (sim_near_dup + reranker); tag sources.
   - Artifact: ClusterBundle { cluster_id, items[], canonical_links[], lang }.

2) Stage 1: Extract Facts (evidence-only)
   - Strictly sourced factual nuggets per cluster; each fact must carry a URL from inputs.
   - Artifact: ClusterFacts { facts: [ { text, url } ] }.

3) Stage 2: Score & Select
   - Scores: actionability(0–3), novelty(0–2), impact(0–2), reusability(0–2), reliability(0–1); agentic_bonus(+1 tie-breaker only).
   - Pick top 1–3 facts per cluster; merge near-duplicates; allow a Strategic/Risk flag.
   - Artifact: ClusterSelection { picked: [ ScoredFact ], dropped: [...] }.

4) Stage 3: Compose Bullets
   - Bullet structure: What changed → How to use → Limits.
   - Provide smallest viable step (command, flag, config); reuse Stage 1 URLs.
   - Artifact: Topic { topic_id, headline, bullets[1–4] }.

5) Stage 4: Global Ordering + Format/QC
   - Deterministic排序：使用 Stage 2 得分排序并调节前三条来源多样性。
   - Agentic Focus 可选编排：将 agentic=true 主题汇总到专栏，避免在主列表重复。
   - 程序化写出最终 JSON（1–4 bullets、URL 校验、去重）。
   - Artifact: Briefing { title, date (UTC ISO8601), topics[] }。

## Prompt Strategy (files)
- prompts/stage1_extract_facts.yaml — evidence-only; forbid speculation; per-fact URL.
- prompts/stage2_score_select.yaml — rubric + concise rationale (internal).
- prompts/stage3_compose_bullets.yaml — enforce 3-part structure + minimal steps.
- prompts/stage4_format_qc.yaml — schema guardrails + JSON repair fallback.
- prompts/daily_briefing_multisource.yaml — toned-down Agentic priority + optional sections.

## Data Models (Python / Pydantic)
- ClusterItem, ClusterBundle, Fact, ClusterFacts, ScoredFact, ClusterSelection, Bullet, Topic, Briefing.

## Reliability Guards
- Schema-first LLM I/O; native structured outputs; repair loop only on failure.
- Determinism: per-stage cache (content hash), retries with backoff, bounded tokens.
- Hallucination controls: Stage 1 URL requirement; Stage 3 must reuse URLs; reject unsourced bullets.
- Safety: strip HTML/JS, cap tokens per cluster, truncate long threads with source-preserving sampler.

## Metrics
- kept_vs_dropped_facts, near_dup_reduction, avg_actionability, agentic_section_present, json_repair_rate.
- Print in make show / view commands; persist summary alongside artifacts.

## Quality Gates (DoD)
- 100% bullets carry valid input URLs.
- Topic bullets 1–4; valid JSON matches schema exactly.
- No duplicate headlines or near-identical bullet texts.
- Tests green; coverage includes all new modules; zero JSON repair in normal runs.

## Risks & Mitigations
- Hallucinations → evidence-only Stage 1 + URL carry-over + schema outputs.
- Over-pruning diversity → ordering QC enforces cross-source coverage; cap per-cluster picks.
- Latency → stage caching; tuned max_tokens; minimal retries.

## Implementation Plan (To‑Do)

[x] Stage 0 — Design Sign‑off
- [x] Document stage IO contracts, errors, caching, metrics (this file).
- [x] Prompt policy update (Agentic tie-breaker + Strategic/Risk allowance).

[x] Stage 1 — Prompts + Models
- [x] Add modular prompts (stage1–4) under prompts/.
- [x] Tweak daily_briefing_multisource.yaml wording as above.
- [x] Add models in briefing/models.py; unit tests instantiate models.

[x] Stage 2 — Orchestrator
- [x] briefing/pipeline_multistep.py with run_stage1/2/3/4 functions.
- [ ] Native structured outputs + JSON repair fallback.
- [x] Cache artifacts under out/<briefing_id>/stages/.

[x] Stage 3 — CLI + Config
- [x] Add CLI flags: --multi-stage, --agentic-section, --brief-lite.
- [x] Config toggles: processing.multi_stage, max_bullets_per_topic, agentic_section, scoring_weights, llm defaults.
- [x] Backward compatibility with single-prompt path.

[x] Stage 4 — Tests + Fixtures
- [x] Fixtures: hn_bundles.json, twitter_bundles.json, reddit_bundles.json.
- [x] Tests: stage schema validity, link presence, bullet bounds, ordering sanity, language, dedup.

[ ] Stage 5 — Metrics + QC
- [x] Emit metrics; show in make show / view-hn.
- [ ] Alert on json_repair_rate > 0.

[ ] Stage 6 — Tuning
- [ ] Adjust per-source thresholds; compare duplicate rate and actionability.
- [ ] Optional brief-lite A/B.

[ ] Stage 7 — Documentation
- [ ] Usage docs, flags, artifacts layout; developer notes for new sources/prompts.

## Milestones
- M1: Prompts + models scaffolded; tests load.
- M2: Orchestrator produces valid artifacts on fixtures.
- M3: CLI integrated; e2e on fixtures; metrics printed.
- M4: Tuning + docs; ready for regular use.
