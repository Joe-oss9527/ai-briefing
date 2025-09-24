#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

log_section() {
    local title="$1"
    printf '\n======================================\n%s\n======================================\n' "$title"
}

run_target() {
    local target="$1"
    log_section "开始执行 ${target} 任务 (MULTI_STAGE=1)"
    if MULTI_STAGE=1 make "$target"; then
        log_section "${target} 任务完成"
    else
        log_section "${target} 任务失败"
        return 1
    fi
}

log_section "启动自动化简报任务"

status=0
if ! run_target "twitter"; then
    status=1
fi
if ! run_target "hn"; then
    status=1
fi

log_section "全部任务结束 (exit_code=${status})"
exit "$status"
