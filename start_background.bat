@echo off
title Start Awaken In Background
cd /d "%~dp0"
wscript.exe "%~dp0start_background.vbs"
echo [OK] Awaken launched silently in the background!
timeout /t 2 >nul
exit
