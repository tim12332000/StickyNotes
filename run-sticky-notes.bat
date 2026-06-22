@echo off
setlocal

rem Use the local venv Python if available.
if exist "%~dp0\.venv\Scripts\python.exe" (
    "%~dp0\.venv\Scripts\python.exe" -m app.main
    exit /b %errorlevel%
)

echo Error: 未找到本機虛擬環境 .venv\Scripts\python.exe
echo 請先在專案資料夾執行：
echo   python -m venv .venv
echo   .\.venv\Scripts\Activate.ps1
echo   pip install -e ".[dev]"
pause
exit /b 1
