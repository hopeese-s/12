@echo off
cd /d "%~dp0"
title OmniLoad - All-in-One Local Media Downloader
cls
python run.py
echo.
echo ============================================================
echo  OmniLoad stopped. Press any key to close this window.
echo ============================================================
pause >nul
