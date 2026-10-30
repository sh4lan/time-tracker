@echo off
setlocal

rem Strip the trailing backslash that %~dp0 carries. Inside quotes, a trailing
rem "\" escapes the closing quote and makes alacritty swallow the rest of the
rem command line as part of the path.
set "DIR=%~dp0"
if "%DIR:~-1%"=="\" set "DIR=%DIR:~0,-1%"

if not exist "%DIR%\main.py" (
    echo main.py not found in "%DIR%"
    pause
    exit /b 1
)

rem Start the tracker, then immediately go live. ctrl-c leaves the live view,
rem which restarts the tracker on its own before the shell prompt returns.
where alacritty >nul 2>&1
if errorlevel 1 (
    echo alacritty not found on PATH, falling back to a normal console window.
    start "time-tracker" cmd /k "cd /d "%DIR%" && python main.py start && python main.py live"
    exit /b 0
)

rem The live command string reaches cmd through alacritty, so keep it to plain
rem args and "&" separators: nested quotes and "&&" do not survive the extra
rem hop out to the shell level.
start "" alacritty --working-directory "%DIR%" -e cmd /k "python main.py start & python main.py live"
exit /b 0
