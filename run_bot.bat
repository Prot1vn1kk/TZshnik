@echo off
REM ========================================
REM Скрипт запуска ТЗшника на Windows
REM ========================================

set "ROOT=%~dp0"
set "BOT_DIR=%ROOT%TelegramBot_v2"
set "VENV_DIR=%ROOT%.venv"

cd /d "%BOT_DIR%" || exit /b 1

REM Проверка виртуального окружения
if not exist "%VENV_DIR%" (
    echo 📦 Создание виртуального окружения...
    python -m venv "%VENV_DIR%"
)

REM Активация виртуального окружения
call "%VENV_DIR%\Scripts\activate.bat"

REM Установка зависимостей
echo 📥 Установка зависимостей...
pip install -q -r "%BOT_DIR%\requirements.txt"

REM Запуск бота
echo 🚀 Запуск ТЗшника...
python -m bot

pause
