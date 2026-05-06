@echo off
echo ========================================
echo   FT-ICR MS - 本地开发环境启动
echo ========================================

set BASEDIR=%~dp0..

echo [1/3] 安装后端依赖...
cd /d "%BASEDIR%\backend"
pip install -r requirements.txt

echo [2/3] 安装前端依赖...
cd /d "%BASEDIR%\frontend"
call npm install

echo [3/3] 启动服务...
echo.
echo   后端: http://localhost:8001
echo   前端: http://localhost:3000
echo   API 文档: http://localhost:8001/docs
echo.

:: Start backend
cd /d "%BASEDIR%\backend"
start "Backend" cmd /c "uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload"

:: Start frontend
cd /d "%BASEDIR%\frontend"
start "Frontend" cmd /c "npm run dev"

echo 所有服务已启动，按任意键停止...
pause > nul
taskkill /FI "WindowTitle eq Backend*" /F 2>nul
taskkill /FI "WindowTitle eq Frontend*" /F 2>nul
echo 服务已停止。
