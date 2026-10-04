@echo off
REM Starts Photo Drop. The access token is kept in .photodrop-token (created on first run).
REM To save somewhere else, add:  --dest "D:\Photos\Meshroom"
cd /d "%~dp0"
py -3 -u server.py %*
pause
