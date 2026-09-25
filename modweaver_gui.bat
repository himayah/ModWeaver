@echo off
rem ------------------------------------------------------------------
rem Start the ModWeaver GUI by double-clicking (for PCs where .pyw has no associated app).
rem Runs modweaver_gui.pyw with pythonw (no console); this window closes right away.
rem   PYW : Python used to start the GUI (default: pythonw; e.g. set PYW=py -3w)
rem Arguments are passed to the GUI (e.g. modweaver_gui.bat --lang=en).
rem This file is ASCII only: cmd misreads multi-byte lines in batch files.
rem ------------------------------------------------------------------
cd /d "%~dp0"
if "%PYW%"=="" set "PYW=pythonw"
where %PYW% >nul 2>nul
if errorlevel 1 (
    echo %PYW% was not found. Install Python 3.10 or later and add it to PATH,
    echo or set the PYW environment variable to the Python that starts the GUI.
    pause
    exit /b 1
)
start "" %PYW% "%~dp0modweaver_gui.pyw" %*
