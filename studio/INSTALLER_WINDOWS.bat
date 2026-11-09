@echo off
chcp 65001 >nul
title Installation de Mon Studio
echo.
echo   ==========================================
echo      Installation de Mon Studio d'animation
echo   ==========================================
echo.
echo   Cela prend 10 a 30 minutes. Windows va demander plusieurs fois
echo   "Voulez-vous autoriser cette application..." : cliquez OUI.
echo.
pause
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\installer_windows.ps1"
echo.
pause
