@echo off
cd /d "%~dp0"
echo Open http://127.0.0.1:8765/ after the server starts.
where py >nul 2>nul
if errorlevel 1 (
    python server.py
) else (
    py -3 server.py
)
pause
