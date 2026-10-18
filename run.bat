@echo off
title Awaken Placement Sentinel
cd /d "%~dp0"

if not exist .env (
    echo [!] No .env file found. Creating .env from .env.example...
    copy .env.example .env
    echo [*] Please edit .env and add your TELEGRAM_BOT_TOKEN.
    notepad .env
)

echo Starting Awaken...
python main.py
pause
