# Repository Guidelines

## Project Structure & Module Organization
Core pipeline code lives in `briefing/` with adapters in `sources/`, renderers in `rendering/`, schema assets in `schemas/`, and helpers such as `pipeline.py` and `utils.py`. The CLI entry point is `cli.py`, invoked by the Docker worker. Configuration blueprints sit in `configs/`, prompt templates in `prompts/`, and utility scripts in `scripts/`. Generated briefs appear under `out/<briefing_id>/` (excluded from version control). Mirror this layout when adding modules, and place tests alongside counterparts in `tests/`.

## Build, Test, and Development Commands
- `make setup`: bootstrap Python, Rust, TEI, and model downloads.
- `make start` / `make stop`: control the docker stack plus the TEI process.
- `make hn`, `make twitter`, `make reddit`, `make all`: execute the ingestion-to-summary pipeline per source.
- `make show` or `make view-hn`: print the latest briefing artifacts.
- `./scripts/validate_config.py --config configs/<file>.yaml`: validate new briefing configs with the JSON schema.
- `./run_tests.sh`: run `python -m pytest tests/ -v --cov=. --cov-report=term-missing`.

## Coding Style & Naming Conventions
Target Python 3.11, 4-space indentation, and type hints when data crosses module boundaries. Use `snake_case` for modules and functions, `PascalCase` for classes, and descriptive constants in ALL_CAPS near the top of files. Prefer `briefing.utils.get_logger(__name__)` over `print`, keep side effects behind functions, and ensure configuration defaults surface via environment-aware constants. YAML or JSON schema additions belong in `briefing/schemas/` with UTF-8 reads.

## Testing Guidelines
Write `pytest` suites using `test_<subject>.py` naming (see `tests/test_pipeline.py`). Co-locate fixtures with their tests and rely on `pytest.mark` categories for slow or integration work. Exercise error branches so `--cov-report=term-missing` remains empty, and gate new features on `./run_tests.sh`. Replace external API calls with fakes or recorded payloads to keep the pipeline deterministic.

## Commit & Pull Request Guidelines
History follows lightweight Conventional commits (`feat:`, `fix:`, `refactor:`, `cleanup:`, `update:`). Keep summaries under roughly 60 characters, imperative, and scoped to one logical change. Pull requests should explain the outcome, list configuration or migration impacts, and attach screenshots when output formatting shifts. Link issues, call out follow-up items, and note the `make` or test commands you executed.

## Configuration & Security Tips
Copy `.env.example` to `.env`, store secrets locally, and avoid checking them in. Validate YAML config changes before running pipelines, and prefer minimal-scope API credentials. `output.telegram` now supports `disable_link_preview`, `timeout_sec`, `retries`, and optional inline `bot_token`; keep parse mode at `HTML` unless you map the Markdown precisely. `output.github_backup` expects `<org>/<repo>` plus committer metadata—set `token_env` or `token` with least-privilege scopes. Service overrides belong in `docker-compose.override.yml` so shared `make start` behaviour stays predictable.
`TEI_MODE` controls whether the embeddings service runs in the Docker stack (`compose`, default) or via the Metal-friendly local binary (`local`); keep `TEI_ORIGIN` aligned with the chosen mode.
