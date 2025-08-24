
# Patch Notes (Clean Upgrade)

Date: 2025-08-24

## Highlights
- Added **OpenAI** provider; kept Gemini & OpenAI.
- Switched to **JSON-only** LLM response and **local Markdown rendering**.
- Added `schemas/briefing.schema.json` for strict output validation.
- Strengthened prompts (`prompts/daily_briefing_multisource.yaml`, `prompts/daily_briefing_multisource.yaml`).
- New CLI: `cli.py`.

## Files Added
- `briefing/llm_adapters.py`
- `briefing/md_renderer.py`
- `briefing/output_validator.py`
- `schemas/briefing.schema.json`
- `cli.py`
- `.env.example`
- `README_INTEGRATION.md`, `README_PATCH.md`

## Files Updated
- `summarizer.py`
- `schemas/config.schema.json` (+openai fields)
- `requirements.txt` (+openai)
- `prompts/daily_briefing_multisource.yaml` (style rules)
- `prompts/daily_briefing_multisource.yaml` (JSON-only)

No legacy fallbacks retained.


## 更新：统一 YAML 提示词
- 新增 `prompts/daily_briefing_multisource.yaml`，并在 `summarizer.py` 中优先使用。
- `configs/*.yaml` 已切换为 `summarization.prompt_file` 字段；旧的 `prompt_file`/`prompt_file` 已移除。
- 依赖新增：`pyyaml`、`jinja2`。

