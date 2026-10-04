@echo off
REM Starts Photo Drop. The file .photodrop-token contains the access token. Photo Drop makes this file when it starts for the first time.
REM To use a different save folder, add:  --dest "D:\Photos\Meshroom"
cd /d "%~dp0"
py -3 -u server.py %*
pause
