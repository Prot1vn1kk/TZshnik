#!/bin/bash
# ==============================================
# ТЗшник v2.0 - Скрипт установки на VPS
# Для Ubuntu/Debian серверов
# ==============================================

set -e  # Останавливаемся при ошибках

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════╗"
echo "║       ТЗшник v2.0 - Установка на VPS      ║"
echo "╚═══════════════════════════════════════════╝"
echo -e "${NC}"

# Получаем текущую директорию
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CURRENT_USER=$(whoami)

echo "📁 Директория проекта: $PROJECT_DIR"
echo "👤 Пользователь: $CURRENT_USER"
echo ""

# ==============================================
# 1. Проверка системы
# ==============================================
echo -e "${GREEN}[1/6] Проверка системы...${NC}"

# Проверка Python
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
    echo "✅ Python: $PYTHON_VERSION"
else
    echo -e "${RED}❌ Python3 не найден!${NC}"
    echo "Установите Python: sudo apt install python3 python3-venv python3-pip"
    exit 1
fi

# Проверка версии Python (нужна 3.10+)
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
    echo -e "${RED}❌ Требуется Python 3.10 или выше!${NC}"
    echo "Текущая версия: $PYTHON_VERSION"
    exit 1
fi

# ==============================================
# 2. Создание виртуального окружения
# ==============================================
echo -e "\n${GREEN}[2/6] Создание виртуального окружения...${NC}"

cd "$PROJECT_DIR"

if [ -d "venv" ]; then
    echo "⚠️ Виртуальное окружение уже существует"
    read -p "Пересоздать? (y/N): " RECREATE
    if [ "$RECREATE" = "y" ] || [ "$RECREATE" = "Y" ]; then
        rm -rf venv
        python3 -m venv venv
        echo "✅ Виртуальное окружение пересоздано"
    fi
else
    python3 -m venv venv
    echo "✅ Виртуальное окружение создано"
fi

# Активация
source venv/bin/activate
echo "✅ Виртуальное окружение активировано"

# ==============================================
# 3. Установка зависимостей
# ==============================================
echo -e "\n${GREEN}[3/6] Установка зависимостей...${NC}"

pip install --upgrade pip wheel setuptools
pip install -r requirements.txt

echo "✅ Зависимости установлены"

# ==============================================
# 4. Настройка конфигурации
# ==============================================
echo -e "\n${GREEN}[4/6] Настройка конфигурации...${NC}"

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "✅ Файл .env создан из .env.example"
        echo -e "${YELLOW}⚠️ ВАЖНО: Отредактируйте .env файл!${NC}"
        echo "   nano .env"
    else
        echo -e "${RED}❌ Файл .env.example не найден!${NC}"
        exit 1
    fi
else
    echo "✅ Файл .env уже существует"
fi

# Создание директорий
mkdir -p data exports logs
chmod 755 data exports logs
echo "✅ Директории созданы"

# ==============================================
# 5. Установка systemd сервиса
# ==============================================
echo -e "\n${GREEN}[5/6] Настройка systemd сервиса...${NC}"

# Создаём конфиг сервиса с правильными путями
SERVICE_FILE="$SCRIPT_DIR/tzshnik-bot.service"

if [ -f "$SERVICE_FILE" ]; then
    # Обновляем пути в файле сервиса
    TEMP_SERVICE="/tmp/tzshnik-bot.service"
    
    cat > "$TEMP_SERVICE" << EOF
[Unit]
Description=ТЗшник v2.0 Telegram Bot
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
Group=$CURRENT_USER

WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/python -m bot.main

Restart=always
RestartSec=10

MemoryMax=256M

Environment=PYTHONUNBUFFERED=1
Environment=PYTHONDONTWRITEBYTECODE=1

StandardOutput=append:$PROJECT_DIR/logs/bot.log
StandardError=append:$PROJECT_DIR/logs/error.log

TimeoutStopSec=30
KillSignal=SIGTERM

[Install]
WantedBy=multi-user.target
EOF

    echo "📋 Сервис сконфигурирован"
    echo ""
    echo "Для установки сервиса выполните:"
    echo -e "${YELLOW}"
    echo "  sudo cp $TEMP_SERVICE /etc/systemd/system/tzshnik-bot.service"
    echo "  sudo systemctl daemon-reload"
    echo "  sudo systemctl enable tzshnik-bot"
    echo "  sudo systemctl start tzshnik-bot"
    echo -e "${NC}"
else
    echo "⚠️ Файл сервиса не найден, пропускаем..."
fi

# ==============================================
# 6. Права на скрипты
# ==============================================
echo -e "\n${GREEN}[6/6] Установка прав на скрипты...${NC}"

chmod +x "$SCRIPT_DIR"/*.sh 2>/dev/null || true
echo "✅ Права установлены"

# ==============================================
# Готово!
# ==============================================
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         ✅ Установка завершена!           ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════╝${NC}"
echo ""
echo "📝 Следующие шаги:"
echo ""
echo "1. Отредактируйте .env файл:"
echo "   ${YELLOW}nano $PROJECT_DIR/.env${NC}"
echo ""
echo "2. Запустите бота вручную (для теста):"
echo "   ${YELLOW}cd $PROJECT_DIR && ./scripts/start.sh${NC}"
echo ""
echo "3. Или установите и запустите systemd сервис:"
echo "   ${YELLOW}sudo cp /tmp/tzshnik-bot.service /etc/systemd/system/${NC}"
echo "   ${YELLOW}sudo systemctl daemon-reload${NC}"
echo "   ${YELLOW}sudo systemctl enable tzshnik-bot${NC}"
echo "   ${YELLOW}sudo systemctl start tzshnik-bot${NC}"
echo ""
echo "4. Проверьте статус:"
echo "   ${YELLOW}./scripts/status.sh${NC}"
echo "   или: ${YELLOW}sudo systemctl status tzshnik-bot${NC}"
echo ""
