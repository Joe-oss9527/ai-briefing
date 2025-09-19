#!/bin/bash
# AI Briefing Schedule Management Script

SERVICE_NAME="com.ai-briefing.twitter"
PLIST_PATH="$HOME/Library/LaunchAgents/${SERVICE_NAME}.plist"

case "$1" in
    start)
        echo "Starting AI Briefing Twitter service..."
        launchctl start "$SERVICE_NAME"
        ;;
    stop)
        echo "Stopping AI Briefing Twitter service..."
        launchctl stop "$SERVICE_NAME"
        ;;
    status)
        echo "Checking AI Briefing Twitter service status..."
        launchctl list | grep "$SERVICE_NAME" || echo "Service not found"
        ;;
    reload)
        echo "Reloading AI Briefing Twitter service..."
        launchctl unload "$PLIST_PATH" 2>/dev/null
        launchctl load "$PLIST_PATH"
        ;;
    logs)
        echo "Showing recent logs..."
        echo "=== Output Logs ==="
        tail -20 logs/launchd_out.log 2>/dev/null || echo "No output logs found"
        echo ""
        echo "=== Error Logs ==="
        tail -20 logs/launchd_error.log 2>/dev/null || echo "No error logs found"
        ;;
    *)
        echo "Usage: $0 {start|stop|status|reload|logs}"
        echo ""
        echo "Commands:"
        echo "  start   - Start the service manually"
        echo "  stop    - Stop the service"
        echo "  status  - Check if service is loaded"
        echo "  reload  - Reload the service configuration"
        echo "  logs    - Show recent logs"
        exit 1
        ;;
esac