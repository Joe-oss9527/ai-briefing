
CONFIG ?= configs/ai-briefing-twitter-list.yaml
PY ?= python3

# AI-Briefing 便捷命令
# 使用: make [命令]

.PHONY: help start stop restart status start-tei stop-tei hn twitter reddit all show view-hn view-twitter view-reddit logs clean-output build check-services check-deps install-deps install-tei clean-tei download-models setup validate run


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
	@echo "  make start-tei      - 启动本地 TEI 服务"
	@echo "  make stop-tei       - 停止本地 TEI 服务"
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
	@echo "安装和配置:"
	@echo "  make setup         - 🚀 一键安装所有依赖 (推荐新用户)"
	@echo "  make check-deps    - 检查系统依赖状态"
	@echo "  make install-deps  - 安装系统依赖 (Rust, git-lfs)"
	@echo "  make install-tei   - 编译安装 TEI (Metal GPU)"
	@echo "  make download-models - 下载 AI 模型文件"
	@echo "  make clean-tei     - 清理 TEI 相关文件"
	@echo ""
	@echo "构建优化:"
	@echo "  make build         - 构建优化镜像 (多阶段构建)"
	@echo ""
	@echo "其他:"
	@echo "  make logs          - 查看实时日志"
	@echo "  make clean-output  - 清理 7 天前的输出文件"
	@echo "======================================"

# ========== 服务管理 ==========

start:
	@echo "🚀 启动 AI-Briefing 服务..."
	@echo "  构建优化的生产镜像..."
	@docker compose build --build-arg BUILDKIT_INLINE_CACHE=1
	@echo "  启动 Docker 服务..."
	@docker compose up -d
	@echo "  启动本地 TEI 服务 (Metal GPU)..."
	@./scripts/start-tei.sh > /dev/null 2>&1 &
	@echo "⏳ 等待服务就绪..."
	@sleep 8
	@echo "✅ 所有服务已启动！"
	@make check-services

stop:
	@echo "🛑 停止 AI-Briefing 服务..."
	@docker compose down
	@pkill -f text-embeddings-router || echo "  TEI 服务未在运行"
	@echo "✅ 所有服务已停止"

restart:
	@echo "🔄 重启 AI-Briefing 服务..."
	@make stop
	@make start

status:
	@echo "📊 服务状态："
	@docker compose ps

start-tei:
	@echo "⚡ 启动本地 TEI 服务 (Metal GPU)..."
	@./scripts/start-tei.sh &
	@sleep 3
	@echo "✅ TEI 服务已启动！"

stop-tei:
	@echo "🛑 停止本地 TEI 服务..."
	@pkill -f text-embeddings-router || echo "TEI 服务未在运行"
	@echo "✅ TEI 服务已停止"

check-services:
	@echo "🔍 检查服务健康状态..."
	@echo -n "  TEI (嵌入服务): "
	@curl -s http://localhost:8080/health > /dev/null 2>&1 && echo "✅ 正常" || echo "❌ 异常"
	@echo -n "  RSSHub (数据源): "
	@curl -s http://localhost:1200/healthz > /dev/null 2>&1 && echo "✅ 正常" || echo "❌ 异常"

# ========== 数据收集任务 ==========

hn:
	@echo "======================================"
	@echo "📰 开始收集 Hacker News 摘要"
	@echo "======================================"
	@echo "⏳ 处理阶段: 获取数据 → 文本嵌入 → 聚类分析 → 生成摘要"
	@echo ""
	@docker compose run --rm worker cli.py --config configs/ai-briefing-hackernews.yaml
	@echo ""
	@echo "✅ Hacker News 收集完成！"
	@echo "📁 输出位置: out/ai-briefing-hackernews/"
	@ls -lht out/ai-briefing-hackernews/*.md 2>/dev/null | head -1 || echo "   (暂无输出文件)"

twitter:
	@echo "======================================"
	@echo "🐦 开始收集 Twitter Dev Tools 摘要"
	@echo "======================================"
	@echo "⏳ 处理阶段: 获取数据 → 文本嵌入 → 聚类分析 → 生成摘要"
	@echo ""
	@docker compose run --rm worker cli.py --config configs/ai-briefing-twitter-list.yaml
	@echo ""
	@echo "✅ Twitter 收集完成！"
	@echo "📁 输出位置: out/ai-briefing-twitter-list/"
	@ls -lht out/ai-briefing-twitter-list/*.md 2>/dev/null | head -1 || echo "   (暂无输出文件)"

reddit:
	@echo "======================================"
	@echo "🤖 开始收集 Reddit GameDev 摘要"
	@echo "======================================"
	@echo "⏳ 处理阶段: 获取数据 → 文本嵌入 → 聚类分析 → 生成摘要"
	@echo ""
	@docker compose run --rm worker cli.py --config configs/ai-briefing-reddit.yaml
	@echo ""
	@echo "✅ Reddit 收集完成！"
	@echo "📁 输出位置: out/ai-briefing-reddit/"
	@ls -lht out/ai-briefing-reddit/*.md 2>/dev/null | head -1 || echo "   (暂无输出文件)"

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
	@ls -lht out/ai-briefing-hackernews/*.md 2>/dev/null | head -3 || echo "   暂无文件"
	@echo ""
	@echo "📁 Twitter Dev Tools:"
	@ls -lht out/ai-briefing-twitter-list/*.md 2>/dev/null | head -3 || echo "   暂无文件"
	@echo ""
	@echo "📁 Reddit GameDev:"
	@ls -lht out/ai-briefing-reddit/*.md 2>/dev/null | head -3 || echo "   暂无文件"

view-hn:
	@echo "======================================"
	@echo "📖 Hacker News 最新摘要"
	@echo "======================================"
	@echo ""
	@cat out/ai-briefing-hackernews/$$(ls -t out/ai-briefing-hackernews/*.md 2>/dev/null | head -1 | xargs basename) 2>/dev/null || echo "暂无内容"

view-twitter:
	@echo "======================================"
	@echo "📖 Twitter Dev Tools 最新摘要"
	@echo "======================================"
	@echo ""
	@cat out/ai-briefing-twitter-list/$$(ls -t out/ai-briefing-twitter-list/*.md 2>/dev/null | head -1 | xargs basename) 2>/dev/null || echo "暂无内容"

view-reddit:
	@echo "======================================"
	@echo "📖 Reddit GameDev 最新摘要"
	@echo "======================================"
	@echo ""
	@cat out/ai-briefing-reddit/$$(ls -t out/ai-briefing-reddit/*.md 2>/dev/null | head -1 | xargs basename) 2>/dev/null || echo "暂无内容"

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

# ========== 构建优化 ==========

build:
	@echo "🏗️  构建优化镜像..."
	@echo "  使用多阶段构建减少镜像大小..."
	@DOCKER_BUILDKIT=1 docker compose build --build-arg BUILDKIT_INLINE_CACHE=1
	@echo "✅ 优化镜像构建完成！"
	@echo "📊 查看镜像大小："
	@docker images | grep ai-briefing-worker || docker images | grep worker

# ========== 开发调试 ==========

check-deps:
	@echo "🔍 检查系统依赖..."
	@echo -n "  Docker: "
	@docker --version > /dev/null 2>&1 && echo "✅ 已安装" || echo "❌ 未安装"
	@echo -n "  Docker Compose: "
	@docker compose version > /dev/null 2>&1 && echo "✅ 已安装" || echo "❌ 未安装"
	@echo -n "  Rust: "
	@rustc --version > /dev/null 2>&1 && echo "✅ 已安装" || echo "❌ 未安装"
	@echo -n "  Cargo: "
	@cargo --version > /dev/null 2>&1 && echo "✅ 已安装" || echo "❌ 未安装"
	@echo -n "  git-lfs: "
	@git lfs version > /dev/null 2>&1 && echo "✅ 已安装" || echo "❌ 未安装"
	@echo -n "  TEI Binary: "
	@test -f ~/.cargo/bin/text-embeddings-router && echo "✅ 已安装" || echo "❌ 未安装"
	@echo -n "  fastText Model: "
	@test -f lid.176.bin && echo "✅ 已安装" || echo "❌ 未安装"

install-deps:
	@echo "📦 安装系统依赖..."
	@echo "正在检查并安装缺失的依赖..."
	@if ! rustc --version > /dev/null 2>&1; then \
		echo "  安装 Rust..."; \
		curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y; \
		source ~/.cargo/env; \
	fi
	@if ! git lfs version > /dev/null 2>&1; then \
		echo "  安装 git-lfs..."; \
		if command -v brew > /dev/null; then \
			brew install git-lfs; \
		else \
			echo "  ❌ 请手动安装 git-lfs"; \
			exit 1; \
		fi \
	fi
	@echo "✅ 依赖安装完成！"

install-tei:
	@echo "🛠️  编译安装 TEI (Metal GPU 支持)..."
	@if test -f ~/.cargo/bin/text-embeddings-router; then \
		echo "  TEI 已安装，跳过编译"; \
	else \
		echo "  正在克隆 TEI 源码..."; \
		rm -rf /tmp/tei-build; \
		cd /tmp && GIT_LFS_SKIP_SMUDGE=1 git clone https://github.com/huggingface/text-embeddings-inference.git tei-build; \
		cd /tmp/tei-build && git restore --source=HEAD :/; \
		echo "  正在编译 TEI (此过程需要 3-5 分钟)..."; \
		cd /tmp/tei-build && cargo install --path router -F metal; \
		echo "  验证安装..."; \
		test -f ~/.cargo/bin/text-embeddings-router && echo "  ✅ TEI 编译安装成功！" || (echo "  ❌ TEI 安装失败"; exit 1); \
		rm -rf /tmp/tei-build; \
	fi

clean-tei:
	@echo "🗑️  清理 TEI 相关文件..."
	@rm -rf /tmp/tei-build
	@if test -f ~/.cargo/bin/text-embeddings-router; then \
		echo "  移除 TEI 二进制文件..."; \
		rm -f ~/.cargo/bin/text-embeddings-router; \
	fi
	@echo "✅ TEI 清理完成"

download-models:
	@echo "📥 下载 AI 模型文件..."
	@if test -f lid.176.bin; then \
		echo "  fastText 模型已存在，跳过下载"; \
	else \
		echo "  正在下载 fastText 语言识别模型 (125MB)..."; \
		wget -O lid.176.bin https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin; \
		echo "  验证文件完整性..."; \
		if test -f lid.176.bin && test $$(stat -f%z lid.176.bin 2>/dev/null || stat -c%s lid.176.bin 2>/dev/null) -gt 100000000; then \
			echo "  ✅ fastText 模型下载完成！"; \
		else \
			echo "  ❌ 模型文件下载失败或不完整"; \
			rm -f lid.176.bin; \
			exit 1; \
		fi \
	fi

setup:
	@echo "======================================"
	@echo "🚀 AI-Briefing 一键安装"
	@echo "======================================"
	@echo "此过程将自动安装所有必需组件："
	@echo "  • 系统依赖 (Rust, git-lfs)"
	@echo "  • TEI 文本嵌入服务 (Metal GPU)"
	@echo "  • AI 模型文件"
	@echo ""
	@make install-deps
	@echo ""
	@make install-tei
	@echo ""
	@make download-models
	@echo ""
	@echo "🔍 最终验证..."
	@make check-deps
	@echo ""
	@echo "🎉 安装完成！现在您可以使用："
	@echo "  make start      - 一键启动所有服务 (Docker + TEI)"
	@echo "  make all        - 收集所有数据源"
	@echo "  make show       - 查看生成的摘要文件"
	@echo "======================================"

test-config:
	@echo "🔍 验证配置文件..."
	@docker compose run --rm worker python -c "from utils import validate_config; import yaml; import sys; \
		configs = ['configs/ai-briefing-hackernews.yaml', 'configs/ai-briefing-twitter-list.yaml', 'configs/ai-briefing-reddit.yaml']; \
		for c in configs: \
			print(f'Checking {c}...'); \
			with open(c) as f: cfg = yaml.safe_load(f); \
			validate_config(cfg); \
		print('✅ All configs valid!')"

shell:
	@echo "🐚 进入 Worker 容器 Shell..."
	@docker compose run --rm worker /bin/bash

validate:
	$(PY) scripts/validate_config.py --config $(CONFIG)

run:
	$(PY) cli.py --config $(CONFIG)

