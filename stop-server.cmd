@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop-server.ps1" %*
