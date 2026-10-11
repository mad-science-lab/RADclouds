@echo off
REM Version: V26.284.1723
REM Double-click to start RADclouds and open it in your browser.
cd /d "%~dp0"
python -m radclouds web %*
pause
