#!/bin/bash

# AI-Briefing 便捷收集脚本
# 带彩色进度提示和状态反馈

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 进度动画
spinner() {
    local pid=$1
    local delay=0.1
    local spinstr='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
    while [ "$(ps a | awk '{print $1}' | grep $pid)" ]; do
        local temp=${spinstr#?}
        printf " [%c]  " "$spinstr"
        local spinstr=$temp${spinstr%"$temp"}
        sleep $delay
        printf "\b\b\b\b\b\b"
    done
    printf "    \b\b\b\b"
}

# 显示进度阶段
show_stage() {
    local stage=$1
    case $stage in
        1) echo -e "${CYAN}📡 阶段 1/4: 获取数据源...${NC}" ;;
        2) echo -e "${CYAN}🔍 阶段 2/4: 文本嵌入与处理...${NC}" ;;
        3) echo -e "${CYAN}🤖 阶段 3/4: 聚类分析与排序...${NC}" ;;
        4) echo -e "${CYAN}📝 阶段 4/4: 生成摘要...${NC}" ;;
    esac
}

# 运行任务并监控进度
run_task() {
    local config=$1
    local name=$2
    local briefing_id=${config//_daily/}
    briefing_id=${briefing_id//_/-}
    
    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}🚀 开始收集: $name${NC}"
    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    # 显示处理流程
    echo -e "${BLUE}处理流程:${NC}"
    echo -e "  📡 获取数据 → 🔍 文本处理 → 🤖 智能聚类 → 📝 生成摘要"
    echo ""
    
    # 创建临时日志文件
    local temp_log="/tmp/brief_${config}_$$.log"
    
    # 后台运行任务
    docker compose run --rm worker orchestrator.py --config configs/$config.yaml > $temp_log 2>&1 &
    local pid=$!
    
    # 监控日志并更新进度
    local current_stage=0
    while kill -0 $pid 2>/dev/null; do
        if grep -q "fetched items=" $temp_log 2>/dev/null && [ $current_stage -lt 1 ]; then
            current_stage=1
            show_stage 1
            local items=$(grep "fetched items=" $temp_log | tail -1 | grep -oE "items=[0-9]+" | cut -d= -f2)
            [ -n "$items" ] && echo -e "  ${GREEN}✓ 获取 $items 条数据${NC}"
        fi
        
        if grep -q "processed bundles=" $temp_log 2>/dev/null && [ $current_stage -lt 2 ]; then
            current_stage=2
            show_stage 2
            local bundles=$(grep "processed bundles=" $temp_log | tail -1 | grep -oE "bundles=[0-9]+" | cut -d= -f2)
            [ -n "$bundles" ] && echo -e "  ${GREEN}✓ 生成 $bundles 个主题簇${NC}"
        fi
        
        if grep -q "summarized took_ms=" $temp_log 2>/dev/null && [ $current_stage -lt 3 ]; then
            current_stage=3
            show_stage 3
        fi
        
        if grep -q "output written" $temp_log 2>/dev/null && [ $current_stage -lt 4 ]; then
            current_stage=4
            show_stage 4
        fi
        
        sleep 1
    done
    
    wait $pid
    local exit_code=$?
    
    echo ""
    
    if [ $exit_code -eq 0 ]; then
        # 检查是否为空简报
        if grep -q "empty briefing -> skip" $temp_log 2>/dev/null; then
            echo -e "${YELLOW}⚠️  $name: 当前时间窗口内无内容（空简报）${NC}"
            echo -e "${YELLOW}   系统已跳过文件生成${NC}"
        else
            echo -e "${GREEN}✅ $name 收集完成！${NC}"
            
            # 显示输出信息
            local output_dir="out/${briefing_id//-/_}"
            echo -e "${GREEN}📁 输出位置: $output_dir${NC}"
            
            # 显示最新文件信息
            local latest_file=$(ls -t $output_dir/*.md 2>/dev/null | head -1)
            if [ -n "$latest_file" ]; then
                echo -e "${GREEN}📄 最新文件: $(basename $latest_file)${NC}"
                local file_size=$(ls -lh $latest_file | awk '{print $5}')
                local line_count=$(wc -l < $latest_file)
                echo -e "${GREEN}   大小: $file_size | 行数: $line_count${NC}"
                
                # 显示摘要统计
                local topics=$(grep -c "^##" $latest_file 2>/dev/null || echo "0")
                echo -e "${GREEN}   主题数: $topics${NC}"
            fi
        fi
    else
        echo -e "${RED}❌ $name 收集失败！${NC}"
        echo -e "${RED}错误信息:${NC}"
        tail -5 $temp_log
    fi
    
    # 清理临时日志
    rm -f $temp_log
    echo ""
}

# 显示所有输出
show_all_outputs() {
    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}📊 所有输出文件状态${NC}"
    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    for dir in out/*/; do
        if [ -d "$dir" ]; then
            local name=$(basename "$dir")
            echo -e "${CYAN}📁 $name:${NC}"
            
            local md_files=$(find "$dir" -name "*.md" -type f 2>/dev/null | wc -l)
            local json_files=$(find "$dir" -name "*.json" -type f 2>/dev/null | wc -l)
            local html_files=$(find "$dir" -name "*.html" -type f 2>/dev/null | wc -l)
            
            echo -e "   Markdown: $md_files 个文件"
            echo -e "   JSON: $json_files 个文件"
            echo -e "   HTML: $html_files 个文件"
            
            # 显示最新的3个文件
            echo -e "   ${GREEN}最新文件:${NC}"
            ls -lht "$dir"/*.md 2>/dev/null | head -3 | while read line; do
                echo "     $line"
            done
            echo ""
        fi
    done
}

# 查看指定源的最新内容
view_latest() {
    local source=$1
    local dir="out/${source}"
    local latest=$(ls -t $dir/*.md 2>/dev/null | head -1)
    
    if [ -n "$latest" ]; then
        echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${YELLOW}📖 查看: $(basename $latest)${NC}"
        echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo ""
        less "$latest"
    else
        echo -e "${YELLOW}⚠️  $dir 目录下暂无输出文件${NC}"
    fi
}

# 主菜单
case "$1" in
    hn|hackernews)
        run_task "hackernews_daily" "Hacker News"
        ;;
    twitter)
        run_task "twitter_dev_tools" "Twitter Dev Tools"
        ;;
    reddit)
        run_task "reddit_gamedev" "Reddit GameDev"
        ;;
    all)
        echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${YELLOW}🔄 收集所有数据源${NC}"
        echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo ""
        run_task "hackernews_daily" "Hacker News"
        run_task "twitter_dev_tools" "Twitter Dev Tools"
        run_task "reddit_gamedev" "Reddit GameDev"
        echo -e "${GREEN}🎉 所有任务完成！${NC}"
        ;;
    show)
        show_all_outputs
        ;;
    view)
        case "$2" in
            hn|hackernews)
                view_latest "hackernews_daily"
                ;;
            twitter)
                view_latest "twitter_dev_tools"
                ;;
            reddit)
                view_latest "reddit_gamedev"
                ;;
            *)
                echo -e "${RED}请指定要查看的源: hn, twitter, reddit${NC}"
                ;;
        esac
        ;;
    status)
        echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${YELLOW}🔍 服务状态检查${NC}"
        echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo ""
        
        echo -n "TEI 嵌入服务: "
        curl -s http://localhost:8080/health > /dev/null 2>&1 && echo -e "${GREEN}✅ 正常${NC}" || echo -e "${RED}❌ 异常${NC}"
        
        echo -n "Ollama LLM服务: "
        curl -s http://localhost:11434/api/tags > /dev/null 2>&1 && echo -e "${GREEN}✅ 正常${NC}" || echo -e "${RED}❌ 异常${NC}"
        
        echo -n "RSSHub 数据源: "
        curl -s http://localhost:1200/healthz > /dev/null 2>&1 && echo -e "${GREEN}✅ 正常${NC}" || echo -e "${RED}❌ 异常${NC}"
        ;;
    help|*)
        echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${YELLOW}AI-Briefing 收集脚本${NC}"
        echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo ""
        echo "使用方法: $0 {命令} [参数]"
        echo ""
        echo -e "${CYAN}收集命令:${NC}"
        echo "  hn/hackernews  - 收集 Hacker News 摘要"
        echo "  twitter        - 收集 Twitter Dev Tools 摘要"
        echo "  reddit         - 收集 Reddit GameDev 摘要"
        echo "  all            - 收集所有数据源"
        echo ""
        echo -e "${CYAN}查看命令:${NC}"
        echo "  show           - 显示所有输出文件状态"
        echo "  view {source}  - 查看指定源的最新摘要"
        echo "                   例: $0 view hn"
        echo ""
        echo -e "${CYAN}其他命令:${NC}"
        echo "  status         - 检查服务状态"
        echo "  help           - 显示此帮助信息"
        echo ""
        echo -e "${GREEN}示例:${NC}"
        echo "  $0 hn          # 收集 Hacker News"
        echo "  $0 all         # 收集所有源"
        echo "  $0 view hn     # 查看最新 HN 摘要"
        exit 0
        ;;
esac