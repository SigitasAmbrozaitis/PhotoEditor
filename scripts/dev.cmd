@echo off
rem Starts backend + UI dev server. See dev.ps1 for details.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0dev.ps1" %*
