# 【最终版】可扩展简报生成平台 - 实施部署指南（v2）
**包含**：Hacker News 适配器、Telegram 推送、GitHub 仓库备份、空简报跳过生成/推送、结构化日志。  
**目标读者**：DevOps / 平台工程 / 具备 Docker 使用经验的开发者。

---

## 0. 快速结论（TL;DR）
- 复制 `.env.example` → `.env`，填好密钥（Gemini/Telegram/GitHub/Reddit/Twitter）。  
- `docker compose up -d --build` 拉起 **RSSHub / TEI / Ollama / Redis / Browserless**。  
- （可选）通过 Ollama API 预拉 `qwen2.5:7b-instruct`、`llama3.1:8b-instruct`。  
- 运行任务：  
  ```bash
  docker compose run --rm worker orchestrator.py --config configs/hackernews_daily.yaml
  ```
- 结果位于 `out/<briefing_id>/briefing_*.md|json|html`；若当天内容为空，**不会**生成文件或推送。

---

## 1. 项目目录结构
```
ai-briefing/
├─ configs/
│  ├─ _template.yaml
│  ├─ twitter_dev_tools.yaml
│  ├─ reddit_gamedev.yaml
│  └─ hackernews_daily.yaml
├─ schemas/
│  └─ config.schema.json
├─ adapters/
│  ├─ __init__.py
│  ├─ twitter_list_adapter.py
│  ├─ rss_adapter.py
│  ├─ reddit_adapter.py
│  └─ hackernews_adapter.py
├─ prompts/
│  ├─ system_common.txt
│  └─ template_daily.txt
├─ out/
│  └─ .gitkeep
├─ orchestrator.py
├─ pipeline.py
├─ summarizer.py
├─ publisher.py
├─ utils.py
├─ docker-compose.yml
├─ Dockerfile.worker
├─ requirements.txt
├─ .env.example
└─ README.md
```

> 说明：`out/` 为输出目录（运行后生成）；`schemas/config.schema.json` 会对配置进行强校验，第一时间发现错误。

---

## 2. 环境要求
- Docker 24+ / Docker Compose v2+
- Linux / macOS（Windows 需启用 WSL2）
- 能访问 Hugging Face、Ollama、Telegram、GitHub（按需）
- CPU 环境可运行；大批量任务建议独立 GPU 的 TEI 与加速推理

---

## 3. 配置文件
### 3.1 `.env.example`（复制为 `.env` 并填写）
- 服务地址：`RSSHUB_ORIGIN` / `TEI_ORIGIN` / `OLLAMA_ORIGIN`
- Twitter：`TWITTER_AUTH_TOKEN`（可逗号分隔轮换）、`TWITTER_THIRD_PARTY_API`（可选）
- Reddit：`REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` / `REDDIT_USER_AGENT`
- LLM：`GEMINI_API_KEY`
- Telegram：`TELEGRAM_BOT_TOKEN`
- GitHub：`GITHUB_TOKEN`、`GIT_AUTHOR_NAME`、`GIT_AUTHOR_EMAIL`
- 日志：`LOG_LEVEL`、`LOG_DIR`、`LOG_JSON`

> **安全**：`.env` 不应提交版本库。日志中会对常见密钥进行打码。

### 3.2 `configs/*.yaml`（任务配置）
- **source**：数据源（`twitter_list` / `rss` / `reddit` / `hackernews`）及其参数；HN 支持 `hn_story_type: top|new|best`、`hn_limit`。  
- **processing**：时间窗、聚类最小簇大小、近重复阈值、BGE-Reranker 型号、候选上限。  
- **summarization**：`llm_provider`（gemini/ollama）、模型名、提示词模板、目标主题数。  
- **output**：输出目录、格式（`md/json/html`）、**telegram** 推送块、**github_backup** 备份块。

> **空简报策略**：当聚类后 `bundles` 为空或 LLM 输出的 `topics` 为空，系统**不会**写文件，也**不会**执行任何推送。

---

## 4. 依赖与镜像
### 4.1 `requirements.txt`
- 修正了 `torch` 的源写法（`--index-url` 独立成行）
- 主要依赖：`faiss-cpu`, `hdbscan`, `sentence-transformers`, `fasttext-wheel`, `google-genai`, `praw`, `tenacity` 等

### 4.2 `Dockerfile.worker`
- 安装 `git/openssh` 以支持 GitHub 备份推送
- 预下载 fastText 语言识别模型 `lid.176.bin`

### 4.3 `docker-compose.yml`
- 服务：`rsshub`、`browserless`、`redis`、`tei`、`ollama`、`worker`
- 健康检查：RSSHub/TEI/Ollama 均配置了 `healthcheck`
- `worker` 通过 `depends_on` + 启动时主动探测，避免“冷启动即请求”导致的 5xx

---

## 5. 启动与自测
```bash
# 1) 构建并启动基础设施
docker compose up -d --build

# 2) （可选）预拉 Ollama 指令模型（亦可在首次调用时自动拉取）
curl http://localhost:11434/api/pull -d '{"name":"qwen2.5:7b-instruct"}'
curl http://localhost:11434/api/pull -d '{"name":"llama3.1:8b-instruct"}'

# 3) 运行示例任务（Hacker News）
docker compose run --rm worker orchestrator.py --config configs/hackernews_daily.yaml

# 4) 查看输出（若非空简报）
ls -la out/hackernews_daily
```

---

## 6. Telegram 推送
在任务配置中开启：
```yaml
output:
  dir: "out/hackernews_daily"
  formats: ["md","json"]
  telegram:
    enabled: true
    chat_id: "@your_channel_or_chat_id"
    parse_mode: "None"   # None|Markdown|MarkdownV2|HTML
    chunk_size: 3500
```
- 在 `.env` 设置 `TELEGRAM_BOT_TOKEN`。  
- 系统会自动把超长 Markdown 切片发送。  
- 使用 `MarkdownV2/HTML` 时需确保转义正确（模板未强制开启）。

---

## 7. GitHub 仓库备份
在任务配置中开启：
```yaml
output:
  github_backup:
    enabled: true
    repo_url: "https://github.com/yourname/briefing-backup.git"
    repo_dir: "."
    branch: "main"
    commit_message_prefix: "hn-daily"
    # pathspec: ""   # 留空默认只提交本任务 output.dir
```
- 在 `.env` 设置 `GITHUB_TOKEN`（建议 PAT，HTTPS 方式）。  
- 首次运行会自动初始化仓库/远端并推送。  
- 若无变更，自动跳过提交与推送。

---

## 8. 运行与运维最佳实践
- **计划任务**：
  ```bash
  0 7 * * * cd /path/to/ai-briefing && docker compose run --rm worker orchestrator.py --config configs/hackernews_daily.yaml >> /var/log/ai-briefing.cron.log 2>&1
  ```
- **性能**：大规模数据建议先分桶或使用 ANN 近邻筛后再聚类与精排；`max_candidates_per_cluster` 控制交叉编码器上限。
- **安全**：避免在日志与 PR 中泄露 `.env`；必要时对输出进行去标识化处理。

---

## 9. 故障排查
- **无输出**：检查是否命中“空简报”条件（内容确实为空时不会产生任何文件/推送）。  
- **TEI 404/5xx**：确认 `http://localhost:8080/health` 为 200；或检查 Docker 端口映射。  
- **Ollama 无模型**：使用 `/api/pull` 拉取；或在第一次请求时等待拉取完成。  
- **Telegram 失败**：检查 `chat_id` 与 `TELEGRAM_BOT_TOKEN`；查看日志中的错误信息（已打码）。  
- **GitHub 失败**：确认 `GITHUB_TOKEN` 权限、`repo_url` 可写、`repo_dir` 是 git 仓库；查看日志中 `git$` 调用结果（敏感已打码）。

---

## 10. 附录：示例任务（完整）
- `configs/hackernews_daily.yaml`  
- `configs/twitter_dev_tools.yaml`  
- `configs/reddit_gamedev.yaml`  
- `configs/_template.yaml`

> 配置字段含义与枚举详见 `schemas/config.schema.json`。

---

**版本标记**：v2（含 HN/Telegram/GitHub/空简报/日志增强）

> 本项目已采用 **Docker Compose Spec**（不再使用顶层 `version:` 字段），请使用 `docker compose` v2 CLI。


> 已新增 **.gitignore** 与 **.dockerignore**：默认忽略 `.env`、`logs/`、`out/`、缓存与字节码等，不会误入版本库或构建上下文。
