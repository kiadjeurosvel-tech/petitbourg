# Demarre Mon Studio en arriere-plan (sans fenetre) puis ouvre le navigateur.
$Studio = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Studio
$env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User") + ";" + "$env:LOCALAPPDATA\Microsoft\WinGet\Links"
$Url = "http://127.0.0.1:8765"
function Up { try { (Invoke-WebRequest "$Url/api/health" -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200 } catch { $false } }
if (-not (Up)) {
  New-Item -ItemType Directory -Force donnees | Out-Null
  # pythonw.exe : processus totalement independant, sans console (survit a la fermeture de toute fenetre)
  $Pyw = "$Studio\.venv\Scripts\pythonw.exe"
  if (-not (Test-Path $Pyw)) { $Pyw = "$Studio\.venv\Scripts\python.exe" }
  Start-Process -FilePath $Pyw -ArgumentList "-m", "serveur" -WorkingDirectory $Studio -WindowStyle Hidden
  for ($i = 0; $i -lt 60 -and -not (Up); $i++) { Start-Sleep -Milliseconds 500 }
}
$Ts = "$env:ProgramFiles\Tailscale\tailscale.exe"
if (Test-Path $Ts) { $p = Start-Process $Ts -ArgumentList "serve", "--bg", "8765" -WindowStyle Hidden -PassThru; if (-not $p.WaitForExit(8000)) { $p.Kill() } }
if (-not $env:STUDIO_SANS_NAVIGATEUR) { Start-Process $Url }
