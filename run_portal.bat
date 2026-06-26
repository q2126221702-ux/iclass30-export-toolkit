@echo off
chcp 65001 >nul
cd /d "%~dp0"
python open_portal.py
pause
