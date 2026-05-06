@echo off
setlocal

set BASEDIR=%~dp0
set VENV=%BASEDIR%.venv
set VENV_PY=%VENV%\Scripts\python.exe
set SYSTEM_PY=C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe
set BACKEND=%BASEDIR%backend
set FRONTEND=%BASEDIR%frontend

echo ========================================
echo   FT-ICR MS Web Platform
echo ========================================

REM Check/create venv
if exist "%VENV_PY%" (
    echo [OK] venv exists
    goto install_deps
)

echo [1/2] Creating venv...
if not exist "%SYSTEM_PY%" (
    echo [ERROR] Python not found: %SYSTEM_PY%
    pause
    exit /b 1
)
"%SYSTEM_PY%" -m venv "%VENV%"
if errorlevel 1 (
    echo [ERROR] Failed to create venv
    pause
    exit /b 1
)
echo [OK] venv created

:install_deps
echo [2/2] Installing dependencies...
"%VENV_PY%" -m pip install -r "%BACKEND%\requirements.txt" --quiet
echo [OK] Dependencies ready

echo.
echo ========================================
echo   Starting services...
echo ========================================

REM Start backend
echo [Backend] http://localhost:8001
start "FTICRMS-Backend" /D "%BACKEND%" "%VENV_PY%" -m uvicorn app.main:app --host 127.0.0.1 --port 8001

REM Wait for backend
timeout /t 5 /nobreak >nul

REM Start frontend
echo [Frontend] http://localhost:3000
start "FTICRMS-Frontend" /D "%FRONTEND%" cmd /c "npm run dev"

echo.
echo ========================================
echo   All services started!
echo.
echo   Frontend:  http://localhost:3000
echo   Backend:   http://localhost:8001
echo   API Docs:  http://localhost:8001/docs
echo.
echo   Close Backend/Frontend windows to stop
echo ========================================
echo.
pause
