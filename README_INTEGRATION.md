
# Integration Notes (Unified LLM + JSON-only Renderer)

This project now uses **JSON-only LLM output** and renders Markdown locally for stability.

## What changed
- `summarizer.py` expects **only JSON** from the model and validates it via `schemas/briefing.schema.json`.
- LLM provider is pluggable via `briefing/llm/registry.py` and supports **OpenAI / Gemini**.
- CLI entry added: `cli.py --config configs/ai-briefing-hackernews.yaml`.

## Config
```yaml
summarization:
  openai_model: "gpt-4o-mini"
  gemini_model: "gemini-2.0-flash-exp"
  target_item_count: 10
```


## 统一 YAML 提示词
- 现在优先使用 `prompts/daily_briefing_multisource.yaml`（System+Task 一体，Jinja 占位）。
- 配置写法（示例）：
```yaml
summarization:
  llm_provider: "openai"
  openai_model: "gpt-4o-mini"
  prompt_file: "prompts/daily_briefing_multisource.yaml"
  target_item_count: 8
```


## Makefile（默认指向分源配置）
```bash
make install
make validate CONFIG=configs/ai-briefing-hackernews.yaml
make run CONFIG=configs/ai-briefing-twitter-list.yaml
```

## Docker / Compose（默认 Twitter 配置，可覆盖）
```bash
docker build -t ai-briefing:latest .
docker run --rm --env-file .env -v $(pwd)/configs:/app/configs -v $(pwd)/prompts:/app/prompts -v $(pwd)/schemas:/app/schemas -v $(pwd)/output:/app/output ai-briefing:latest --config configs/ai-briefing-twitter-list.yaml

# 或
docker compose up --build
# 也可覆盖：
docker compose run --rm ai-briefing --config configs/ai-briefing-hackernews.yaml
```


## 非破坏式对接你现有的 Make/Docker
- 我不会直接覆盖你的 `Makefile` / `Dockerfile` / `docker-compose.yml`。
- 参考样例在 `ops_samples/`，如需快速追加入口：
```bash
python scripts/ops_patch.py          # 只在缺失时追加 make validate / make run
make validate CONFIG=configs/xxxx.yaml
make run CONFIG=configs/xxxx.yaml
```


> 注：已自动从 merged_code.txt 恢复你仓库原有的运维文件（Makefile/Dockerfile/docker-compose.yml），我们提供的样例位于 ops_samples/，并提供 scripts/ops_patch.py 可选追加新入口（非覆盖）。

## 关于 Dockerfile.worker
你的仓库使用 `Dockerfile.worker`。本包不会覆盖该文件；
如果需要手动构建镜像，请使用：
```bash
docker build -f Dockerfile.worker -t ai-briefing:latest .
docker run --rm --env-file .env   -v $(pwd)/configs:/app/configs   -v $(pwd)/prompts:/app/prompts   -v $(pwd)/schemas:/app/schemas   -v $(pwd)/output:/app/output   ai-briefing:latest --config configs/ai-briefing-twitter-list.yaml
```
若 compose 中已指定 dockerfile 路径，继续沿用你现有配置即可。


## 入口与命令（已追加统一目标）
- 已在你现有 Makefile 中追加：
  - `make validate`：校验 `$(CONFIG)` 与 `schemas/config.schema.json`
  - `make run`：调用 `cli.py --config $(CONFIG)`
- 变量：
  - `PY`（默认 `python3`）、`CONFIG`（默认 `configs/ai-briefing-twitter-list.yaml`）
- 覆盖示例：
```bash
make validate CONFIG=configs/ai-briefing-hackernews.yaml
make run CONFIG=configs/ai-briefing-twitter-list.yaml
```

