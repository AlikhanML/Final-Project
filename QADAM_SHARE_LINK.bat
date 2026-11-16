@echo off
setlocal EnableExtensions DisableDelayedExpansion
title Qadam - Share link

set "QADAM_ORIGIN=http://localhost:8501"
set "QADAM_CLOUDFLARED=D:\DOWNLOAD\cloudflared-windows-amd64.exe"
if not exist "%QADAM_CLOUDFLARED%" set "QADAM_CLOUDFLARED=%~dp0cloudflared-windows-amd64.exe"
if not exist "%QADAM_CLOUDFLARED%" goto missing_cloudflared

call :qadam_running
if not errorlevel 1 goto tunnel

curl.exe --silent --fail --noproxy "*" --max-time 2 "%QADAM_ORIGIN%/_stcore/health" >nul 2>&1
if not errorlevel 1 goto check_local_app

if not exist "%~dp0START_WINDOWS.bat" goto missing_launcher
pushd "%~dp0" || goto missing_launcher
set "STREAMLIT_SERVER_PORT=8501"
echo Starting Qadam. The first launch may take a few minutes.
start "Qadam" "%ComSpec%" /d /c call START_WINDOWS.bat
popd

for /L %%I in (1,1,90) do (
    call :qadam_running
    if not errorlevel 1 goto tunnel
    timeout /t 2 /nobreak >nul
)
goto check_local_app

:tunnel
echo.
echo Copy the https://...trycloudflare.com URL from the Cloudflare output.
echo Keep both Qadam and this window open while sharing.
echo.
"%QADAM_CLOUDFLARED%" tunnel --url "%QADAM_ORIGIN%"
if errorlevel 1 goto tunnel_failed
exit /b 0

:qadam_running
curl.exe --silent --fail --noproxy "*" --max-time 2 "%QADAM_ORIGIN%/component/ui.navigation.qadam_navigation/index.html" 2>nul | findstr.exe /L /C:"summary-destination" >nul
exit /b %errorlevel%

:missing_cloudflared
echo Cloudflared was not found at D:\DOWNLOAD\cloudflared-windows-amd64.exe.
echo You can place cloudflared-windows-amd64.exe next to this file.
goto fail

:missing_launcher
echo Put this file in the emergency_route folder next to START_WINDOWS.bat.
goto fail

:check_local_app
echo Qadam's city map was not found at %QADAM_ORIGIN%.
echo Check the Qadam window and open its Astana map at %QADAM_ORIGIN%.
echo If another app is using port 8501, close it, then run this file again.
goto fail

:tunnel_failed
echo Cloudflare stopped with an error. See its output above.

:fail
pause
exit /b 1
