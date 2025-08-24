
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

AI-Briefing is an extensible briefing generation platform that aggregates content from multiple sources (Twitter, RSS, Reddit, Hacker News), processes it through an ML pipeline (embedding, deduplication, clustering, reranking), and generates summaries using LLMs (Gemini/OpenAI).

## Key Commands

### Quick Start with Makefile (Recommended)
```bash
# Installation and setup
make setup         # 🚀 One-click install all dependencies (Rust, TEI, models)
make check-deps    # Check system dependency status
make install-deps  # Install system dependencies (Rust, git-lfs)
make install-tei   # Compile install TEI (Metal GPU)
make download-models # Download AI model files
make clean-tei     # Clean TEI related files

# Service management
make start          # Start all services
make stop           # Stop all services
make restart        # Restart all services
make status         # Check service status
make start-tei      # Start local TEI service
make stop-tei       # Stop local TEI service
make check-services # Health check all services

# Data collection (with progress indicators)
make hn            # Collect Hacker News
make twitter       # Collect Twitter Dev Tools
make reddit        # Collect Reddit GameDev
make all           # Collect all sources in parallel

# View outputs
make show          # List latest generated files
make view-hn       # View latest HN summary content
make view-twitter  # View latest Twitter summary
make view-reddit   # View latest Reddit summary

# Monitoring
make logs          # View real-time logs
make clean-output  # Clean files older than 7 days
```

### Alternative: Shell Script with Colors
```bash
# Using brief.sh for colored progress tracking
./brief.sh hn          # Collect with visual progress
./brief.sh all         # Collect all with progress
./brief.sh show        # Show all outputs
./brief.sh view hn     # View specific summary
./brief.sh status      # Check service health
```

### Direct Docker Commands
```bash
# Note: TEI now runs locally with Metal GPU acceleration
docker compose up -d --build

# Run a briefing task
docker compose run --rm worker orchestrator.py --config configs/ai-briefing-hackernews.yaml

curl http://localhost:11434/api/pull -d '{"name":"qwen2.5:7b-instruct"}'
curl http://localhost:11434/api/pull -d '{"name":"llama3.1:8b-instruct"}'

# Run tests
docker compose run --rm worker pytest tests/ -v

# Run security tests specifically
docker compose run --rm worker pytest tests/test_security.py -v

# View logs
docker compose logs -f worker
tail -f logs/ai-briefing.log

# Stop all services
docker compose down
```

### Debugging
```bash
# Check service health
make check-services  # Or use direct commands:
curl http://localhost:8080/health     # TEI embedding service
curl http://localhost:1200/healthz    # RSSHub

# Run with debug logging
LOG_LEVEL=DEBUG docker compose run --rm worker orchestrator.py --config configs/ai-briefing-hackernews.yaml

# Test individual adapters
docker compose run --rm worker python -c "from adapters import hackernews_adapter; print(hackernews_adapter.fetch({'hn_story_type': 'top', 'hn_limit': 5}))"

# Enter worker shell for debugging
make shell  # Or: docker compose run --rm worker /bin/bash
```

## Architecture & Key Design Patterns

### Core Flow
1. **Orchestrator** (`orchestrator.py`) - Entry point that coordinates the entire pipeline
   - Validates config via JSON Schema
   - Manages run_id for distributed tracing
   - Implements "empty briefing" strategy (skip file generation if no content)

2. **Data Adapters** (`adapters/*.py`) - Unified interface for diverse sources
   - All adapters implement `fetch(config) -> List[Dict]` returning standardized items
   - Each item has: `id`, `text`, `url`, `author`, `timestamp`, `metadata`
   - Twitter adapter uses RSSHub proxy, Reddit uses PRAW, HN uses Firebase API

3. **Processing Pipeline** (`pipeline.py`) - ML-driven content processing
   - Time window filtering based on `processing.time_window_hours`
   - Text embedding via TEI service (Qwen3-Embedding-0.6B model)
   - Near-duplicate detection using cosine similarity (O(n²) - performance concern for large datasets)
   - HDBSCAN clustering with configurable `min_cluster_size`
   - BGE-Reranker cross-encoding for topic relevance scoring
   - Returns bundles sorted by cluster size

4. **Summarization** (`summarizer.py`) - LLM interaction layer
   - Template-based prompt construction (potential injection risk - use caution)
   - Structured JSON + Markdown output generation
   - Returns `None` for empty briefings to trigger skip logic

5. **Publishing** (`publisher.py`) - Multi-channel distribution
   - Telegram: Auto-chunking for long messages, configurable parse_mode
   - GitHub: Git command whitelist for security, automatic repo initialization
   - Credential handling via environment variables (tokenized URLs)

### Configuration System
- **YAML configs** (`configs/*.yaml`) define tasks declaratively
- **JSON Schema** (`schemas/config.schema.json`) validates all configs
- **Environment variables** (`.env`) for secrets and service endpoints
- Three-tier separation: deployment config (.env), business logic (YAML), code (Python)

### Security Considerations
- Git commands are whitelisted in `publisher._run_safe()`
- Secrets are redacted in logs via `utils.redact_secrets()`
- Docker containers run as non-root user (see `Dockerfile.worker`)
- LLM prompt injection risk exists in `summarizer._mk_prompt()` - needs template engine

### Performance Bottlenecks
- Near-duplicate detection is O(n²) in `pipeline._near_duplicate_mask()`
- Full cosine similarity matrix computed in memory
- BGE reranker processes candidates sequentially
- For large-scale processing, consider batch processing or approximate algorithms

### Service Dependencies
- **TEI** (Text Embeddings Inference): Critical for embedding generation
  - **NEW**: Runs locally with Metal GPU acceleration for Apple Silicon
  - Model: `sentence-transformers/all-MiniLM-L6-v2` (optimized for compatibility)
  - Installation: Use `make install-tei` for native compilation with Metal support
- **RSSHub**: Only needed for Twitter sources
- **Redis**: Cache backend for RSSHub
- **Browserless**: Headless browser for RSSHub scraping

### Output Structure
```
out/
└── <briefing_id>/
    ├── briefing_YYYYMMDDTHHMMSSZ.md
    ├── briefing_YYYYMMDDTHHMMSSZ.json
    └── briefing_YYYYMMDDTHHMMSSZ.html
```

Empty briefings produce no output files and skip all publishing steps.

## Configuration Examples

### Minimal task config
```yaml
briefing_id: "test"
briefing_title: "Test Briefing"
source:
  type: "hackernews"
  hn_story_type: "top"
  hn_limit: 50
processing:
  time_window_hours: 24
  min_cluster_size: 3
  sim_near_dup: 0.9
  reranker_model: "BAAI/bge-reranker-v2-m3"
summarization:
  prompt_file: "prompts/daily_briefing_multisource.yaml"
  target_item_count: 10
output:
  dir: "out/test"
  formats: ["md", "json"]
```

### Required environment variables
```bash
# For Reddit source
REDDIT_CLIENT_ID=xxx
REDDIT_CLIENT_SECRET=xxx

# For Gemini LLM
GEMINI_API_KEY=xxx

# For Telegram publishing
TELEGRAM_BOT_TOKEN=xxx

# For GitHub backup
GITHUB_TOKEN=xxx
```

## Adding New Features

### New Data Source
1. Create `adapters/new_source_adapter.py` with `fetch(config)` function
2. Add source type to `schemas/config.schema.json` enum
3. Add elif branch in `orchestrator._fetch_items()`
4. Create config in `configs/new_source.yaml`

### New Output Channel
1. Create publisher function in `publisher.py`
2. Add config schema in `schemas/config.schema.json`
3. Call from `orchestrator.main()` with error handling

## Troubleshooting

### TEI Service Issues
**Problem**: TEI Docker issues on Apple Silicon (ARM64 architecture)
**Root Cause**: Docker TEI images don't support ARM64 natively, causing performance issues
**Solution**: Use native TEI installation with Metal GPU acceleration
```bash
# Install TEI locally with Metal support
make install-tei

# Start local TEI service
make start-tei

# TEI runs on localhost:8080 with Metal GPU acceleration
```

**Legacy Docker Solution** (not recommended for Apple Silicon):
```yaml
tei:
  image: ghcr.io/huggingface/text-embeddings-inference:cpu-latest  # Use latest, not 1.5
  command: ["--model-id", "sentence-transformers/all-MiniLM-L6-v2"]
```

### Worker Container Issues
**Problem**: "can't open file '/workspace/sleep'" or command execution errors
**Root Cause**: Incorrect command format in docker-compose.yml
**Solution**:
```yaml
worker:
  command: ["python", "-c", "import time; time.sleep(999999999)"]  # Correct Python syntax
```

### Network Connectivity Issues
**Problem**: Worker containers can't resolve service hostnames (e.g., 'tei')
**Root Cause**: `docker compose run` doesn't use service network by default
**Solution**: Use `--no-deps` flag in Makefile commands:
```bash
docker compose run --rm --no-deps worker python orchestrator.py --config ...
```

### Common Docker Commands
```bash
# Check service status
docker compose ps

# View logs for specific service
docker compose logs tei --tail=20

# Test service health manually
curl http://localhost:8080/health     # TEI
curl http://localhost:1200/healthz    # RSSHub

# Clean restart all services
docker compose down && docker compose up -d --build
```
