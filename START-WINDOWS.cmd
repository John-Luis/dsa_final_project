@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto install
where py >nul 2>nul
if errorlevel 1 (
    python -m venv .venv
) else (
    py -3 -m venv .venv
)
if errorlevel 1 goto failed
:install
.venv\Scripts\python.exe -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)"
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo.
echo SerbisyoQ is starting. Open http://127.0.0.1:5000 in your browser.
echo If no custom staff password is configured, use peso-demo.
echo Configure .env privately to enable real confirmation emails.
echo Press Ctrl+C to stop the server.
.venv\Scripts\python.exe -m flask --app serbisyoq.app run --host 127.0.0.1 --port 5000
pause
exit /b
:failed
echo Setup failed. Check the error above. Python 3.11 or newer is required.
pause
exit /b 1
