@echo off
setlocal
cd /d "%~dp0"
echo Starting Smart Crane Incident Review...
echo Keep this window open while using the application.
echo Open http://127.0.0.1:8010 in your browser.
echo.
python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
echo.
echo The server stopped. Review any error shown above.
pause
