#!/bin/bash
# ==============================================
# ТЗшник v2.0 - Проверка статуса бота
# ==============================================

# Цвета
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "📊 Статус бота ТЗшник v2.0"
echo "================================"

# Проверяем процесс
PID=$(pgrep -f "python -m bot" || pgrep -f "python3 -m bot")

if [ -n "$PID" ]; then
    echo -e "Статус: ${GREEN}✅ Запущен${NC}"
    echo "PID: $PID"
    
    # Время работы
    UPTIME=$(ps -o etime= -p "$PID" 2>/dev/null | tr -d ' ')
    echo "Время работы: $UPTIME"
    
    # Использование памяти
    MEM=$(ps -o rss= -p "$PID" 2>/dev/null | tr -d ' ')
    if [ -n "$MEM" ]; then
        MEM_MB=$((MEM / 1024))
        echo "Память: ${MEM_MB} МБ"
    fi
    
    # Использование CPU
    CPU=$(ps -o %cpu= -p "$PID" 2>/dev/null | tr -d ' ')
    if [ -n "$CPU" ]; then
        echo "CPU: ${CPU}%"
    fi
else
    echo -e "Статус: ${RED}❌ Остановлен${NC}"
fi

echo "================================"

# Проверка systemd сервиса (если установлен)
if systemctl is-enabled tzshnik-bot 2>/dev/null | grep -q "enabled"; then
    echo -e "\nSystemd сервис: ${GREEN}включён${NC}"
    systemctl status tzshnik-bot --no-pager -l 2>/dev/null | head -5
fi
