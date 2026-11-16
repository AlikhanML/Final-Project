@echo off
setlocal
cd /d "%~dp0" || goto fail
set "QADAM_PY=.venv\Scripts\python.exe"
if exist "%QADAM_PY%" goto check
where py >nul 2>&1
if errorlevel 1 goto use_python
py -m venv .venv
if errorlevel 1 goto fail
goto check
:use_python
python -m venv .venv
if errorlevel 1 goto fail
:check
"%QADAM_PY%" -c "import sys" >nul 2>&1
if errorlevel 1 goto broken
if not exist ".venv\qadam-requirements.txt" goto install
fc /b requirements.txt ".venv\qadam-requirements.txt" >nul 2>&1
if errorlevel 1 goto install
"%QADAM_PY%" -c "import geopy, streamlit" >nul 2>&1
if errorlevel 1 goto install
goto run
:install
echo Installing Qadam packages into the project .venv ...
"%QADAM_PY%" -m pip install -r requirements.txt
if errorlevel 1 goto fail
"%QADAM_PY%" -c "import geopy, streamlit"
if errorlevel 1 goto fail
copy /y requirements.txt ".venv\qadam-requirements.txt" >nul
if errorlevel 1 goto fail
:run
"%QADAM_PY%" -m streamlit run app.py
if errorlevel 1 goto fail
exit /b 0
:broken
echo The project virtual environment cannot start. Rename .venv to .venv_backup and run this file again.
goto stop
:fail
echo Setup or startup failed. See the error above.
:stop
pause
exit /b 1
