@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  .venv\Scripts\python.exe run_tests.py
) else (
  py run_tests.py
)
set "TEST_EXIT=%ERRORLEVEL%"
if not "%TEST_EXIT%"=="0" echo Tests failed. If dependencies are missing, first run START_WINDOWS.bat.
pause
exit /b %TEST_EXIT%
