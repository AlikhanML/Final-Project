@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  .venv\Scripts\python.exe download_city.py
) else (
  py download_city.py
)
pause
