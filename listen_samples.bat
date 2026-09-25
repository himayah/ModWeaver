@echo off
rem ------------------------------------------------------------------
rem Render the listening samples for DESIGN.md section 11 (3 per item, 375 songs)
rem into output\listen\. The item list and descriptions live in listen_samples.py.
rem Usage: double-click this file, or run it in the repository root.
rem   PY  : Python command (default: python; e.g. set PY=py -3)
rem   FMT : output format (mod / xm / s3m / it / midi / mp3; default mod; mp3 needs ffmpeg)
rem This file is ASCII only: cmd misreads multi-byte lines in batch files.
rem ------------------------------------------------------------------
cd /d "%~dp0"
if "%PY%"=="" set "PY=python"
%PY% "%~dp0listen_samples.py"
pause
