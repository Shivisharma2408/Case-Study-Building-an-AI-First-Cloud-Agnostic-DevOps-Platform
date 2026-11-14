@echo off
rem Windows launcher: runs run.ps1 without changing the PowerShell execution policy.
rem   run setup | up | down | test | pipeline <stage> | bash <script> [args]
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1" %*
exit /b %ERRORLEVEL%
