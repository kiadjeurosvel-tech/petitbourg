# Installation du studio (Windows PowerShell) : powershell -ExecutionPolicy Bypass -File scripts\installer.ps1
Set-Location (Join-Path $PSScriptRoot "..")
if (-not (Test-Path .venv)) { py -3 -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -q --upgrade pip
.\.venv\Scripts\python.exe -m pip install -q -r requirements.txt
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) { "OK FFmpeg" } else { "FFmpeg ABSENT : winget install Gyan.FFmpeg" }
if (Test-Path "C:\Program Files\Blender Foundation") { "OK Blender" } else { "Blender absent : winget install BlenderFoundation.Blender" }
"Voix : .\.venv\Scripts\python.exe scripts\telecharger_voix.py"
"Démarrer : scripts\demarrer.bat"
