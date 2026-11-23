@echo off
setlocal EnableExtensions
rem TSMod Save Editor launcher: finds Python 3.11+ (with Tk) and offers to install it if missing.
rem   TSModSaveEditor.bat            start the editor
rem   TSModSaveEditor.bat --check    only report what was found (for testing)
set "HERE=%~dp0"
set "PY="
set "PYW="

rem 1. The project's own environment (developers).
if defined TSMOD_SKIP_VENV goto :trypy
if exist "%HERE%..\..\.venv\Scripts\pythonw.exe" (
  set "PYW=%HERE%..\..\.venv\Scripts\pythonw.exe"
  goto :found
)

:trypy
rem 2. The "py" launcher that python.org installs. 3. "python" on PATH. Windows' Microsoft Store placeholder fails the
rem    check script, so it is skipped automatically.
for /f "usebackq delims=" %%P in (`py -3 "%HERE%pycheck.py" 2^>nul`) do set "PY=%%P"
if defined PY goto :frompy
for /f "usebackq delims=" %%P in (`python "%HERE%pycheck.py" 2^>nul`) do set "PY=%%P"
if defined PY goto :frompy
goto :missing

:frompy
set "PYW=%PY:python.exe=pythonw.exe%"
if not exist "%PYW%" set "PYW=%PY%"

:found
rem The editor reads the game's data with its own Python pak reader (tools\tspak.py); repak.exe is no longer needed.
if /i "%~1"=="--check" goto :report
start "" "%PYW%" "%HERE%TSModSaveEditor.pyw"
goto :eof

:report
echo Python: %PYW%
goto :eof

:missing
if /i "%~1"=="--check" (
  echo Python: MISSING
  goto :eof
)
echo.
echo  The TSMod Save Editor needs Python 3.11 or newer. It's free, from python.org.
echo.
echo    1  Install it now with winget, Windows' own package manager (official Python release)
echo    2  Open the python.org download page in your browser
echo    3  Cancel
echo.
choice /c 123 /n /m " Choose 1, 2 or 3: "
if errorlevel 3 goto :eof
if errorlevel 2 goto :site
where winget >nul 2>nul
if errorlevel 1 (
  echo.
  echo  winget isn't available on this PC, so the python.org page will open instead.
  goto :site
)
winget install -e --id Python.Python.3.13 --source winget
echo.
echo  When the installer has finished, start TSModSaveEditor.bat again.
pause
goto :eof

:site
start "" "https://www.python.org/downloads/windows/"
echo.
echo  Install Python (keep "Add python.exe to PATH" ticked), then start TSModSaveEditor.bat again.
pause
goto :eof
