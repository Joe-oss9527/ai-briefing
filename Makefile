# AI-Briefing 便捷命令
# 使用: make [命令]

.PHONY: help start stop restart status hn twitter reddit all show view-hn view-twitter view-reddit logs clean-output check-services

# 默认显示帮助
help:
	@echo "======================================"
	@echo "AI-Briefing 命令列表"
	@echo "======================================"
	@echo "服务管理:"
	@echo "  make start          - 启动所有基础服务"
	@echo "  make stop           - 停止所有服务"
	@echo "  make restart        - 重启所有服务"
	@echo "  make status         - 查看服务状态"
	@echo "  make check-services - 检查服务健康状态"
	@echo ""
	@echo "数据收集:"
	@echo "  make hn            - 收集 Hacker News 摘要"
	@echo "  make twitter       - 收集 Twitter Dev Tools 摘要"
	@echo "  make reddit        - 收集 Reddit GameDev 摘要"
	@echo "  make all           - 并行收集所有数据源"
	@echo ""
	@echo "查看输出:"
	@echo "  make show          - 显示最新生成的文件"
	@echo "  make view-hn       - 查看最新 HN 摘要内容"
	@echo "  make view-twitter  - 查看最新 Twitter 摘要内容"
	@echo "  make view-reddit   - 查看最新 Reddit 摘要内容"
	@echo ""
	@echo "其他:"
	@echo "  make logs          - 查看实时日志"
	@echo "  make clean-output  - 清理 7 天前的输出文件"
	@echo "======================================"

# ========== 服务管理 ==========

start:
	@echo "🚀 启动 AI-Briefing 服务..."
	@docker compose up -d --build
	@echo "⏳ 等待服务就绪..."
	@sleep 5
	@echo "✅ 服务已启动！"
	@make check-services

stop:
	@echo "🛑 停止 AI-Briefing 服务..."
	@docker compose down
	@echo "✅ 服务已停止"

restart:
	@echo "🔄 重启 AI-Briefing 服务..."
	@make stop
	@make start

status:
	@echo "📊 服务状态："
	@docker compose ps

check-services:
	@echo "🔍 检查服务健康状态..."
	@echo -n "  TEI (嵌入服务): "
	@curl -s http://localhost:8080/health > /dev/null 2>&1 && echo "✅ 正常" || echo "❌ 异常"
	@echo -n "  Ollama (LLM服务): "
	@curl -s http://localhost:11434/api/tags > /dev/null 2>&1 && echo "✅ 正常" || echo "❌ 异常"
	@echo -n "  RSSHub (数据源): "
	@curl -s http://localhost:1200/healthz > /dev/null 2>&1 && echo "✅ 正常" || echo "❌ 异常"

# ========== 数据收集任务 ==========

hn:
	@echo "======================================"
	@echo "📰 开始收集 Hacker News 摘要"
	@echo "======================================"
	@echo "⏳ 处理阶段: 获取数据 → 文本嵌入 → 聚类分析 → 生成摘要"
	@echo ""
	@docker compose run --rm --no-deps worker python orchestrator.py --config configs/hackernews_daily.yaml
	@echo ""
	@echo "✅ Hacker News 收集完成！"
	@echo "📁 输出位置: out/hackernews_daily/"
	@ls -lht out/hackernews_daily/*.md 2>/dev/null | head -1 || echo "   (暂无输出文件)"

twitter:
	@echo "======================================"
	@echo "🐦 开始收集 Twitter Dev Tools 摘要"
	@echo "======================================"
	@echo "⏳ 处理阶段: 获取数据 → 文本嵌入 → 聚类分析 → 生成摘要"
	@echo ""
	@docker compose run --rm --no-deps worker python orchestrator.py --config configs/twitter_dev_tools.yaml
	@echo ""
	@echo "✅ Twitter 收集完成！"
	@echo "📁 输出位置: out/twitter_dev_tools/"
	@ls -lht out/twitter_dev_tools/*.md 2>/dev/null | head -1 || echo "   (暂无输出文件)"

reddit:
	@echo "======================================"
	@echo "🤖 开始收集 Reddit GameDev 摘要"
	@echo "======================================"
	@echo "⏳ 处理阶段: 获取数据 → 文本嵌入 → 聚类分析 → 生成摘要"
	@echo ""
	@docker compose run --rm --no-deps worker python orchestrator.py --config configs/reddit_gamedev.yaml
	@echo ""
	@echo "✅ Reddit 收集完成！"
	@echo "📁 输出位置: out/reddit_gamedev/"
	@ls -lht out/reddit_gamedev/*.md 2>/dev/null | head -1 || echo "   (暂无输出文件)"

all:
	@echo "======================================"
	@echo "🔄 并行收集所有数据源"
	@echo "======================================"
	@echo "正在启动收集任务..."
	@make hn > /tmp/brief_hn.log 2>&1 & echo "  📰 Hacker News - PID $$!"
	@make twitter > /tmp/brief_twitter.log 2>&1 & echo "  🐦 Twitter - PID $$!"
	@make reddit > /tmp/brief_reddit.log 2>&1 & echo "  🤖 Reddit - PID $$!"
	@echo ""
	@echo "⏳ 等待所有任务完成..."
	@wait
	@echo ""
	@echo "🎉 所有数据源收集完成！"
	@make show

# ========== 查看输出 ==========

show:
	@echo "======================================"
	@echo "📄 最新生成的摘要文件"
	@echo "======================================"
	@echo ""
	@echo "📁 Hacker News:"
	@ls -lht out/hackernews_daily/*.md 2>/dev/null | head -3 || echo "   暂无文件"
	@echo ""
	@echo "📁 Twitter Dev Tools:"
	@ls -lht out/twitter_dev_tools/*.md 2>/dev/null | head -3 || echo "   暂无文件"
	@echo ""
	@echo "📁 Reddit GameDev:"
	@ls -lht out/reddit_gamedev/*.md 2>/dev/null | head -3 || echo "   暂无文件"

view-hn:
	@echo "======================================"
	@echo "📖 Hacker News 最新摘要"
	@echo "======================================"
	@echo ""
	@cat out/hackernews_daily/$$(ls -t out/hackernews_daily/*.md 2>/dev/null | head -1 | xargs basename) 2>/dev/null || echo "暂无内容"

view-twitter:
	@echo "======================================"
	@echo "📖 Twitter Dev Tools 最新摘要"
	@echo "======================================"
	@echo ""
	@cat out/twitter_dev_tools/$$(ls -t out/twitter_dev_tools/*.md 2>/dev/null | head -1 | xargs basename) 2>/dev/null || echo "暂无内容"

view-reddit:
	@echo "======================================"
	@echo "📖 Reddit GameDev 最新摘要"
	@echo "======================================"
	@echo ""
	@cat out/reddit_gamedev/$$(ls -t out/reddit_gamedev/*.md 2>/dev/null | head -1 | xargs basename) 2>/dev/null || echo "暂无内容"

# ========== 日志和维护 ==========

logs:
	@echo "📋 实时日志 (Ctrl+C 退出):"
	@echo "======================================"
	@docker compose logs -f worker --tail=50

clean-output:
	@echo "🗑️  清理 7 天前的输出文件..."
	@find out -name "*.md" -mtime +7 -delete 2>/dev/null || true
	@find out -name "*.json" -mtime +7 -delete 2>/dev/null || true
	@find out -name "*.html" -mtime +7 -delete 2>/dev/null || true
	@echo "✅ 清理完成"

# ========== 开发调试 ==========

test-config:
	@echo "🔍 验证配置文件..."
	@docker compose run --rm --no-deps worker python -c "from utils import validate_config; import yaml; import sys; \
		configs = ['configs/hackernews_daily.yaml', 'configs/twitter_dev_tools.yaml', 'configs/reddit_gamedev.yaml']; \
		for c in configs: \
			print(f'Checking {c}...'); \
			with open(c) as f: cfg = yaml.safe_load(f); \
			validate_config(cfg); \
		print('✅ All configs valid!')"

shell:
	@echo "🐚 进入 Worker 容器 Shell..."
	@docker compose run --rm --no-deps worker /bin/bash