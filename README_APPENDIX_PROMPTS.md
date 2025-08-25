
# 提示词历史对比与迁移附录

本附录记录从**旧的双文件提示词**（`daily_briefing_multisource.yaml` + `daily_briefing_multisource.yaml`）迁移到**统一 YAML 提示词**
（`prompts/daily_briefing_multisource.yaml`）的关键差异与原因，便于审计与回滚时参考。

## 1. 结构对比
- 旧：System 与 Task 分离，调用时需要在代码里拼接，占位符替换较分散。
- 新：**System+Task 一体**的 YAML 文件；通过 Jinja 渲染 `{{ briefing_title }}` 与 `{{ bundles_json }}`；
  LLM 仅产 JSON，Markdown 由本地渲染器统一生成。

## 2. 约束与质量
- bullets：**强约束 1–4 条**，每条包含 `text` 和 `url` 两个字段的结构化对象。
- 链接：每条要点的 `url` 字段包含一个来源链接，取代旧的 `links` 数组。
- 事实边界：明确禁止捏造版本/发布日期/功能/引用；优先官方与一手来源。
- 输出：**仅 JSON**，不产 Markdown；避免 LLM Markdown 漂移导致渲染不稳。

## 3. 配置迁移
- 旧：`summarization.prompt_file` / `summarization.prompt_file`
- 新：`summarization.prompt_file: "prompts/daily_briefing_multisource.yaml"`（**唯一必填**）

额外配置（集中于 `summarization`）
```yaml
temperature: 0.2
timeout: 600
retries: 1
provider_options:
  openai:
    base_url: "${OPENAI_BASE_URL}"
    # http_proxy: "http://127.0.0.1:7890"
    # https_proxy: "http://127.0.0.1:7890"
  gemini:
    api_version: "v1"
    # use_vertex: true
    # project: "your-gcp-project-id"
    # location: "us-central1"
    # host: "https://generativelanguage.googleapis.com"  # Custom Gemini endpoint if needed
```

## 4. 失败模式与稳定性
- 旧：可能“宽容通过”；出现半结构输出或 Markdown 与 JSON 混杂。
- 新：**严格模式**；JSON 解析/Schema 校验不通过 → 直接失败（Fail Fast），产物质量可控。

## 5. 回滚策略（如需）
- 直接切换 `prompt_file` 指向你保存的旧 YAML 版本（不是 `.txt`），保持统一渲染方式；
- **不建议**恢复到 `.txt` 双文件与代码拼接模式，因为这会重新引入隐性不一致。

