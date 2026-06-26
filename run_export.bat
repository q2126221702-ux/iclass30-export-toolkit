@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 关闭旧进程...
taskkill /F /IM python.exe >nul 2>&1
timeout /t 2 /nobreak >nul
echo.
echo ========================================
echo   C30 测验/作业导出（手动导航 + 自动保存）
echo ========================================
echo.
echo 1. 登录后：头像 -^> 学习空间 -^> 课程 -^> 作业考试 -^> 测验
echo 2. 进入详情页（能看到题目和正确答案）
echo 3. 点页面左上角绿色按钮「导出当前页」
echo.
python manual_export.py
pause
