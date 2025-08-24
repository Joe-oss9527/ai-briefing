# 重构说明（Refactor Notes）

## 背景与目标

为提高可维护性与工程一致性，本次重构聚焦以下目标：

* **单一包收敛**：将分散在根目录与子目录的核心代码收敛为一个顶级包，导入边界清晰。
* **契约更强**：LLM **只产 JSON**，本地模板渲染 Markdown，统一走 Schema 校验，杜绝历史混合输出。
* **适配器精简**：保留 **OpenAI Responses API** 与 **Gemini（google-genai/可 Vertex）**；**彻底移除 Ollama**。
* **路径健壮**：所有 Schema/资源以 **相对 `__file__`** 定位，避免工作目录依赖。
* **命名统一**：配置文件统一命名为 `ai-briefing-*.yaml`，标题品牌统一为“**AI 快讯 / AI Digest**”，并在标题中体现来源（Twitter/Hacker News/Reddit）。

---

## 本次变更范围（概览）

* 包名：`ai_briefing/` → **`briefing/`**（导入路径全量更新）
* 入口脚本：`cli_generate_briefing.py` → **`cli.py`**
* LLM 适配：`ai_briefing/llm_adapters.py` → **`briefing/llm/registry.py`**（仅 OpenAI/Gemini）
* 渲染与提示词加载：

  * `ai_briefing/md_renderer.py` → **`briefing/rendering/markdown.py`**
  * `ai_briefing/prompt_loader.py` → **`briefing/rendering/prompt_loader.py`**
* 数据源适配：`adapters/*` → **`briefing/sources/*`**
* Schema：移动到 **`briefing/schemas/`**，并以相对路径加载
* 配置：规范化与重命名（见下）
* Compose/ENV：移除 `ollama` 服务及环境变量

---

## 文件/模块映射对照表

### 包与模块

| 之前                                 | 现在                                             |
| ---------------------------------- | ---------------------------------------------- |
| `ai_briefing/llm_adapters.py`      | **`briefing/llm/registry.py`**                 |
| `ai_briefing/md_renderer.py`       | **`briefing/rendering/markdown.py`**           |
| `ai_briefing/prompt_loader.py`     | **`briefing/rendering/prompt_loader.py`**      |
| `ai_briefing/output_validator.py`  | **`briefing/output_validator.py`**             |
| `orchestrator.py`                  | **`briefing/orchestrator.py`**                 |
| `pipeline.py`                      | **`briefing/pipeline.py`**                     |
| `publisher.py`                     | **`briefing/publisher.py`**                    |
| `utils.py`                         | **`briefing/utils.py`**                        |
| `adapters/twitter_list_adapter.py` | **`briefing/sources/twitter_list_adapter.py`** |
| `adapters/hackernews_adapter.py`   | **`briefing/sources/hackernews_adapter.py`**   |
| `adapters/reddit_adapter.py`       | **`briefing/sources/reddit_adapter.py`**       |
| `adapters/rss_adapter.py`          | **`briefing/sources/rss_adapter.py`**          |
| `schemas/*.json`                   | **`briefing/schemas/*.json`**                  |

### 入口与构建

| 之前                                                 | 现在                           |
| -------------------------------------------------- | ---------------------------- |
| `cli_generate_briefing.py`                         | **`cli.py`**（`Makefile` 已指向） |
| `Makefile run` → `python cli_generate_briefing.py` | **`python cli.py`**          |
| `docker-compose.yml` 含 `ollama` 服务                 | **已移除 `ollama` 服务与依赖**       |
| `.env.example` 含 `OLLAMA_ORIGIN`                   | **已移除**                      |

### 配置文件（`configs/`）

| 之前                      | 现在                                  | 备注                                                               |
| ----------------------- | ----------------------------------- | ---------------------------------------------------------------- |
| `twitter_dev_tools.yaml`    | **`ai-briefing-twitter-list.yaml`** | `briefing_id/output.dir` 同步为同名；`briefing_title: AI 快讯 · Twitter` |
| `hackernews_daily.yaml` | **`ai-briefing-hackernews.yaml`**   | `briefing_title: AI 快讯 · Hacker News`                            |
| `reddit_gamedev.yaml`   | **`ai-briefing-reddit.yaml`**       | `briefing_title: AI 快讯 · Reddit`                                 |
| `_template.yaml`        | `_template.yaml`                    | 模板保留                                                             |

---

## 关键设计决策

1. **LLM 只产 JSON，本地渲染 Markdown**

* `briefing/summarizer.py`：仅读取 `summarization.prompt_file`；无 fallback；对输出做 JSON 解析与 Schema 校验；空主题直接跳过。
* 渲染：`briefing/rendering/markdown.py`；主题标题自动编号（`## 1. ...`），条目为无序列表 `-`，不强制编号条目（可后续按需配置）。

2. **LLM 适配器统一入口（去 Ollama）**

* `briefing/llm/registry.py`：保留 **OpenAI Responses** 与 **Gemini google-genai** 两条路径；全部运行参数来自配置（`temperature/timeout/retries/provider_options`，含 `base_url`、代理、Vertex `project/location/api_version` 等）；无硬编码。
* 彻底移除 Ollama（代码/配置/Compose/文档）。

3. **Schema 与路径**

* `briefing/schemas/config.schema.json`：

  * `summarization.prompt_file` **必填**；
  * `llm_provider` 仅 `gemini|openai`；
  * 包含 `temperature/timeout/retries/provider_options`；
  * 移除 `prompt_system/prompt_template/ollama_model/provider_options.ollama` 等旧键。
* 所有 Schema 通过 **相对包路径** 加载，避免 `cwd` 依赖。

4. **命名规范**

* 配置文件：统一为 `ai-briefing-{platform}[-{feedtype}].yaml`（kebab-case）。
* 标题：品牌“**AI 快讯 / AI Digest**”，在标题中附上来源后缀（Twitter/Hacker News/Reddit）。

---

## 迁移指南（Breaking Changes）

### 1. 导入路径

将所有 `ai_briefing` 导入改为 `briefing`。示例：

```diff
- from ai_briefing.llm_adapters import call_with_options
+ from briefing.llm.registry import call_with_options

- from ai_briefing.md_renderer import render_md
+ from briefing.rendering.markdown import render_md

- from ai_briefing.output_validator import validate_briefing
+ from briefing.output_validator import validate_briefing
```

### 2. CLI/Makefile

```diff
- python cli_generate_briefing.py --config CONFIGS/xxx.yaml
+ python cli.py --config configs/ai-briefing-twitter-list.yaml

- make run CONFIG=configs/old.yaml
+ make run CONFIG=configs/ai-briefing-twitter-list.yaml
```

### 3. 配置键名与约束

* 仅支持 `summarization.prompt_file`（**必须**）；**移除** `prompt_system` / `prompt_template`。
* 仅支持 `llm_provider: gemini|openai`；**移除** `ollama_model` 和 `provider_options.ollama`。
* 输出契约：LLM 只产 JSON；Markdown 由本地渲染。

### 4. Compose/ENV

* 移除 `ollama` 服务与依赖；`.env.example` 不再包含 `OLLAMA_ORIGIN`。
* 如本地有遗留：请执行 `docker compose down -v` 清理旧卷。

---

## 运行与验证

### 快速运行

```bash
pip install -r requirements.txt
make validate                        # 默认 CONFIG=configs/ai-briefing-twitter-list.yaml
make run                             # 产出 out/ai-briefing-twitter-list/*.json & *.md
```

### 其他配置

```bash
make run CONFIG=configs/ai-briefing-hackernews.yaml
make run CONFIG=configs/ai-briefing-reddit.yaml
```

### 测试与质量门

* 语法编译：全项目 **py\_compile 通过**。
* 字符串审查：已清理所有 `ai_briefing`、`ollama` 引用（代码与文档）。
* Schema 校验：`scripts/validate_config.py` 使用包内路径；`make validate` 通过。
* 产物一致性：**JSON→Markdown**；空主题自动跳过发布。

---

## 风险与缓解

* **第三方依赖变更**：建议在生产环境 **锁版本**（`pip-compile` 或 `uv lock`）。
* **旧引用残留**：若外部脚本仍导入 `ai_briefing.*` 会失败；请按“迁移指南#1”批量替换。
* **提示词/模板路径**：仅认 `prompts/daily_briefing_multisource.yaml`；如路径自定义，请在配置中显式指定绝对或相对路径。

---

## 回滚策略

* 若需短期回退：可暂时保留你旧仓库快照或上一压缩包；回滚仅涉及目录/入口与导入路径，不改变业务数据结构。
* 若仅个别模块不兼容：可临时在 `briefing/` 下新增“兼容薄层”转发旧接口（不建议长期保留）。

---

## 后续可选优化（不在本次范围内）

* **包级入口**：添加 `briefing/__main__.py`，支持 `python -m briefing`。
* **安装级命令**：在 `pyproject.toml` 声明 `console_scripts`，一键安装后可直接运行 `briefing --config ...`。
* **渲染主题化**：将 Markdown 的样式参数化（编号/无编号、分隔线、徽章等），不动 JSON 契约。
* **更多来源**：如 YouTube/Substack/RSS，多份 `ai-briefing-*.yaml` 配置并行运行。

---

## 附：下载与文件位置

* **整包下载（最新）**：

  * [ai-briefing-refactor-ai-digest-sourced.zip](sandbox:/mnt/data/ai-briefing-refactor-ai-digest-sourced.zip)
    （包含：`briefing/` 新包结构、`cli.py`、移除 Ollama、三份 `ai-briefing-*` 配置且标题为“AI 快讯 · 来源”）
* 示例运行：

  ```bash
  make validate
  make run
  ```


