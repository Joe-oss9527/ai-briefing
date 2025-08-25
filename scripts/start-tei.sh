#!/bin/bash

# TEI 本地启动脚本
# 使用 Metal GPU 加速的文本嵌入推理服务

set -e

MODEL="${TEI_MODEL:-sentence-transformers/all-MiniLM-L6-v2}"
PORT="${TEI_PORT:-8080}"
TEI_BIN="${HOME}/.cargo/bin/text-embeddings-router"

# 检查 TEI 二进制文件是否存在
if [ ! -f "$TEI_BIN" ]; then
    echo "❌ TEI binary not found at $TEI_BIN"
    echo "Please run: cargo install --path router -F metal"
    exit 1
fi

echo "🚀 Starting TEI with Metal support..."
echo "📍 Model: $MODEL"
echo "🌐 Port: $PORT"
echo "⚡ GPU: Metal (Apple Silicon)"

# 检查端口是否已被占用
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null; then
    echo "⚠️  Port $PORT is already in use"
    echo "Stopping existing service..."
    pkill -f text-embeddings-router || true
    sleep 2
fi

# 启动 TEI 服务
exec "$TEI_BIN" \
    --model-id "$MODEL" \
    --port "$PORT" \
    --revision main \
    --max-client-batch-size 32 \
    --max-batch-tokens 8192