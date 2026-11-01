@echo off
cd /d "%~dp0"
python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/health', timeout=1)" >nul 2>nul && (python open_browser.py & exit /b 0)
python -c "import PIL, imageio_ffmpeg" 2>nul || python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Setup failed. Check Python and internet connection, then run again.
  pause
  exit /b 1
)
python app.py
pause
