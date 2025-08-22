# 【最终版】可扩展简报生成平台 - 架构设计文档（v2）
**范围**：系统设计原则、模块职责、数据契约、算法流程、扩展方式、日志与合规。

---

## 1. 设计原则
- **关注点分离**：`.env`（部署与密钥）、`configs/*.yaml`（业务任务）、`*.py`（核心逻辑）。
- **配置驱动**：所有行为均可通过 YAML 配置，无需改动核心代码。
- **模块化/可插拔**：数据源以适配器模式实现，统一 `fetch(config)->List[Item]` 接口。
- **单一职责**：
  - `orchestrator.py`：编排、校验、健康探测、IO、推送触发。
  - `adapters/*`：抓取与标准化。
  - `pipeline.py`：与源无关的计算（清洗、嵌入、近重复、聚类、精排）。
  - `summarizer.py`：LLM 交互与产出结构化结果（JSON+Markdown）。
  - `publisher.py`：Telegram 与 GitHub 推送。
  - `utils.py`：日志、健康等待、JSONSchema 校验、文本工具、输出写入。
- **开闭原则**：新增数据源或输出渠道无需修改现有核心模块。

---

## 2. 总体架构
```
+-------------------+        +----------------------------------+
|  Orchestrator     |--reads->| configs/*.yaml (声明式任务定义) |
+---------+---------+        +----------------------------------+
          | (1) 选择适配器
          v
+---------+---------+        +----------------------------------+
|  Adapters         |--fetch->| 数据源 (Twitter/RSS/Reddit/HN)  |
+---------+---------+        +----------------------------------+
          | (2) 标准化 Raw Items
          v
+---------+---------+
|  Pipeline         |  嵌入 -> 去重 -> 聚类 -> 候选裁剪 -> BGE精排
+---------+---------+
          | (3) 主题簇 Bundles
          v
+---------+---------+        +----------------------------------+
|  Summarizer       |--LLM-->| Gemini / Ollama                 |
+---------+---------+        +----------------------------------+
          | (4) JSON + Markdown
          v
+---------+---------+        +----------------------------------+
|  Output/Publisher |--->write fs / Telegram / GitHub backup   |
+-------------------+        +----------------------------------+
```

---

## 3. 数据契约
### 3.1 Raw Item（适配器输出）
```json
{
  "id": "string",
  "text": "plain text",
  "url": "string",
  "author": "string",
  "timestamp": "ISO8601",
  "metadata": { "source": "twitter|rss|reddit|hackernews", "...": "..." }
}
```

### 3.2 Bundle（处理管道输出）
```json
{
  "topic_id": "cluster-<int>",
  "topic_label": "string|null",
  "items": [ <Raw Item> ... ]  // 已按重要性排序
}
```

### 3.3 Summarizer 输出
```json
{
  "title": "briefing title",
  "date": "ISO8601",
  "topics": [
    { "topic_id": "...", "headline": "...", "bullets": ["..."], "links": ["..."] }
  ]
}
```
并附同内容的 Markdown 段落。若 `topics` 为空 → 定义为**空简报**。

---

## 4. 核心算法
1. **语言检测**（fastText `lid.176.bin`）：默认仅标注语言，不强制过滤；可在 `pipeline.py` 添加白名单（如 `zh|en`）。  
2. **嵌入**（TEI `Qwen3-Embedding-0.6B`）：`POST /embeddings` 批量向量；可替换其它模型（通过 TEI）。  
3. **近重复过滤**：O(n²) 余弦阈值 `sim_near_dup`（0.90~0.92），降低冗余。  
4. **聚类**（HDBSCAN）：`min_cluster_size` 控制最低簇规模；可引入 UMAP 降维以增强簇形稳定。  
5. **候选裁剪**：按**簇中心**相似度选 `initial_topk`，再限幅 `max_candidates_per_cluster`，保障交叉编码器性能。  
6. **BGE-Reranker 精排**：以“簇中心样本文本”为代理查询进行交叉编码打分，获取主题代表性排序。  
7. **生成**：以模板产出 JSON+Markdown，限制主题数 `target_item_count`。若 `topics` 为空 → 空简报策略生效。

---

## 5. 组件细节
### 5.1 Orchestrator
- 加载配置并通过 `schemas/config.schema.json` 校验；
- 主动等待 TEI/Ollama（以及尽力等待 RSSHub）健康；
- 生成 `run_id`，全链路记录耗时与规模；
- **空简报跳过**：若无 `bundles` 或 `topics` 为空 → **不写文件、不推送**。

### 5.2 Adapters
- **twitter_list**：通过 RSSHub `?format=json`，使用 `email.utils.parsedate_to_datetime` 解析时间，健壮兼容字段差异；
- **rss**：`feedparser` 解析，标题/摘要统一清洗；
- **reddit**：PRAW 只读凭据，支持 `hot/new/rising/top` + `time_window`；
- **hackernews**：Firebase API（`top/new/beststories`），按 `hn_limit` 截断。

### 5.3 Pipeline
- 时间窗过滤 → 语言标注 → 嵌入 → 近重复 → 聚类 → 候选裁剪 → BGE 精排；
- 以簇大小排序输出 Bundles；
- 关键环节记录耗时与数量指标。

### 5.4 Summarizer
- 双通道：`gemini`（`google-genai`）或 `ollama`；
- 以提示词模板生成结构化 JSON + Markdown；
- `topics` 为空时直接返回 `None`（空简报）。

### 5.5 Publisher
- **Telegram**：自动切片、可选 `parse_mode`；失败不影响主流程（记录错误）；
- **GitHub**：支持初始 `git init`、设置/更新 `origin`、只提交 `output.dir`（或 `pathspec`）；
- **敏感信息打码**：命令行回显中不泄露 token。

---

## 6. 可扩展性
### 6.1 新增数据源（示例：X 平台 Space）
1. 新建 `adapters/space_adapter.py` 实现 `fetch`；  
2. 在 `schemas/config.schema.json` 的 `source.type.enum` 中新增 `"space"` 并定义自有字段；  
3. 在 `orchestrator._fetch_items` 加 `elif` 分支；  
4. 新建 `configs/space_daily.yaml` 即可运行。

### 6.2 新增输出渠道（示例：Email/Telegram 频道影子）
- 新建 `publisher_email.py` 提供 `maybe_publish_email()`；  
- 在 `schemas/config.schema.json` 的 `output` 下新增 `email` 配置块；  
- `orchestrator` 中调用。

---

## 7. 日志与可观测性（最佳实践）
- **格式**：默认文本；设置 `LOG_JSON=true` 输出结构化 JSON（含 `ts/level/logger/msg`）。  
- **切割**：`TimedRotatingFileHandler` 按日滚动，保留 7 天（`logs/ai-briefing.log`）。  
- **上下文**：`run_id` 贯穿全链路，关键节点记录 `count` 与 `took_ms`。  
- **隐私**：`redact_secrets()` 自动打码 `.env` 中常见密钥及 URL 中的 `x-access-token`；日志不回显明文 token。  
- **失败策略**：网络异常/推送失败/`git` 出错会记录 `stderr/stdout`（已打码），并尽量不中断其它步骤。  
- **可汇聚**：`LOG_JSON=true` 时建议对接 ELK、OpenSearch、Cloud Logging 等集中式系统。

---

## 8. 安全与合规
- `.env` 永不入库；PR 中避免贴出日志中可能含有的敏感片段；
- 遵守各数据源 ToS/限流策略；必要时增加缓存与退避（`tenacity` 已用于健康等待）；
- 版权与出处：简报中提供原始链接；二次分发注意图片与引用段落的版权界定。

---

## 9. 性能建议
- 大规模抓取：按时间/来源分桶并行处理；或在聚类前以 ANN（FAISS）做近邻筛，降低 O(n²) 重复检测成本；  
- TEI：优先开启 CPU AVX / GPU 加速；批量嵌入控制在数百～数千条/批；  
- 精排：`max_candidates_per_cluster` 控制在 ≤300，更利于 CPU 环境稳定运行。

---

## 10. 版本与演进
- v2：新增 HN 适配器、Telegram 推送、GitHub 备份、空简报策略、日志增强；  
- 后续计划：  
  - 主题命名：以关键词抽取/候选标题投票生成 `topic_label`；  
  - 更丰富的输出：HTML 样式化模板、Email/Slack/飞书推送；  
  - 多语言流程：按语言分簇与分发。

---

**版本标记**：v2（含 HN/Telegram/GitHub/空简报/日志增强）

> 本项目已采用 **Docker Compose Spec**（不再使用顶层 `version:` 字段），请使用 `docker compose` v2 CLI。


> 已新增 **.gitignore** 与 **.dockerignore**：默认忽略 `.env`、`logs/`、`out/`、缓存与字节码等，不会误入版本库或构建上下文。
