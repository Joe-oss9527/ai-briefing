# AI Briefing - 可扩展简报生成平台（v2）

含：Hacker News 适配器、Telegram 推送、GitHub 备份、空简报策略、结构化日志。

## 快速开始
1. 复制 `.env.example` → `.env` 并填写密钥。
2. 启动基础设施：
   ```bash
   docker compose up -d --build
   ```
3. （可选）预拉 Ollama 指令模型：
   ```bash
   curl http://localhost:11434/api/pull -d '{"name":"qwen2.5:7b-instruct"}'
   curl http://localhost:11434/api/pull -d '{"name":"llama3.1:8b-instruct"}'
   ```
4. 执行任务：
   ```bash
   docker compose run --rm worker orchestrator.py --config configs/hackernews_daily.yaml
   ```
5. 输出位置：`out/<briefing_id>/briefing_*.md|json|html`（**空简报不会生成任何文件**）。

完整设计与部署说明见 `docs/AI-Briefing_实施部署指南_v2.md` 与 `docs/AI-Briefing_架构设计文档_v2.md`。

> 本仓库使用 **Docker Compose Spec**（不再使用 `version:` 顶层字段）。请使用 `docker compose`（v2 CLI）。


> 本项目已采用 **Docker Compose Spec**（不再使用顶层 `version:` 字段），请使用 `docker compose` v2 CLI。


> 已新增 **.gitignore** 与 **.dockerignore**：默认忽略 `.env`、`logs/`、`out/`、缓存与字节码等，不会误入版本库或构建上下文。
