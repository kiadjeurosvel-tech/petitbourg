# Installation automatique de Mon Studio (Windows 10/11). Lance par INSTALLER_WINDOWS.bat.
$ErrorActionPreference = "Continue"
$Studio = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Studio

function Etape($n, $t) { Write-Host ""; Write-Host "[$n/7] $t" -ForegroundColor Yellow }
function Ok($t) { Write-Host "   OK  $t" -ForegroundColor Green }
function Ko($t) { Write-Host "   !!  $t" -ForegroundColor Red }
function Refresh-Path {
  $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User") + ";" + "$env:LOCALAPPDATA\Microsoft\WinGet\Links"
}
function Winget-Install($id, $nom) {
  Write-Host "   installation de $nom ..."
  winget install --id $id -e --silent --accept-package-agreements --accept-source-agreements | Out-Null
  Refresh-Path
}

Etape 1 "Verification de Windows"
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
  Ko "L'outil 'winget' est absent. Installez 'App Installer' depuis le Microsoft Store :"
  Write-Host "   https://apps.microsoft.com/detail/9NBLGGH4NNS1"
  Start-Process "https://apps.microsoft.com/detail/9NBLGGH4NNS1"
  exit 1
}
Ok "winget present"

Etape 2 "Installation des logiciels (Python, FFmpeg, Blender, Tailscale)"
Refresh-Path
function Find-Python {
  $c = @("$env:LOCALAPPDATA\Programs\Python\Python312\python.exe", "$env:ProgramFiles\Python312\python.exe",
         "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe", "$env:ProgramFiles\Python313\python.exe",
         "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe", "$env:ProgramFiles\Python311\python.exe")
  foreach ($p in $c) { if (Test-Path $p) { return $p } }
  return $null
}
if (-not (Find-Python)) { Winget-Install "Python.Python.3.12" "Python" }
$Py = Find-Python
if ($Py) { Ok "Python : $Py" } else { Ko "Python introuvable apres installation. Relancez l'installateur."; exit 1 }

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) { Winget-Install "Gyan.FFmpeg" "FFmpeg" }
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) { Ok "FFmpeg" } else { Ko "FFmpeg introuvable (obligatoire). Relancez l'installateur." ; exit 1 }

if (-not (Test-Path "$env:ProgramFiles\Blender Foundation")) { Winget-Install "BlenderFoundation.Blender" "Blender (gros telechargement)" }
if (Test-Path "$env:ProgramFiles\Blender Foundation") { Ok "Blender" } else { Ko "Blender absent : le studio utilisera l'apercu 2D en attendant." }

$Ts = "$env:ProgramFiles\Tailscale\tailscale.exe"
if (-not (Test-Path $Ts)) { Winget-Install "Tailscale.Tailscale" "Tailscale (acces depuis le telephone)" }
if (Test-Path $Ts) { Ok "Tailscale" } else { Ko "Tailscale absent : le studio marchera seulement sur ce PC." }

Etape 3 "Installation du studio"
if (-not (Test-Path ".venv\Scripts\python.exe")) { & $Py -m venv .venv }
$VPy = Join-Path $Studio ".venv\Scripts\python.exe"
& $VPy -m pip install -q --upgrade pip 2>$null
& $VPy -m pip install -q fastapi uvicorn numpy pillow qrcode
& $VPy -m pip install -q piper-tts 2>$null
& $VPy -c "import fastapi, uvicorn, numpy, PIL" 2>$null
if ($LASTEXITCODE -eq 0) { Ok "modules Python" } else { Ko "Echec de l'installation des modules Python."; exit 1 }

Etape 4 "Telechargement des voix francaises"
& $VPy scripts\telecharger_voix.py
& $VPy -c "import piper" 2>$null
if ($LASTEXITCODE -eq 0) { Ok "voix Piper" } else { Ko "Piper indisponible : videos sans voix (le reste fonctionne)." }

Etape 5 "Votre mot de passe"
if (-not (Test-Path "donnees\config.json") -or -not (Select-String -Path "donnees\config.json" -Pattern "password_hash" -Quiet)) {
  Write-Host "   Le mot de passe protege votre studio. Il doit faire AU MOINS 10 caracteres."
  Write-Host "   Exemple : MonStudio2026   (il reste visible pendant la saisie pour eviter les erreurs)"
  while ($true) {
    $mdp = (Read-Host "   Tapez votre mot de passe puis Entree").Trim()
    if ($mdp.Length -lt 10) { Ko "Trop court : $($mdp.Length) caractere(s). Il en faut au moins 10."; continue }
    $conf = (Read-Host "   Retapez-le pour confirmer").Trim()
    if ($conf -ne $mdp) { Ko "Les deux saisies sont differentes. Recommencez."; continue }
    break
  }
  Clear-Host
  $OutputEncoding = New-Object System.Text.UTF8Encoding $false
  $mdp | & $VPy -m serveur mot-de-passe --stdin
  Ok "mot de passe enregistre (notez-le !)"
} else { Ok "mot de passe deja defini" }

Etape 6 "Raccourcis"
$W = New-Object -ComObject WScript.Shell
$Cible = "powershell.exe"
$Arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Studio\scripts\lancer_windows.ps1`""
foreach ($dest in @([Environment]::GetFolderPath("Desktop"), [Environment]::GetFolderPath("Startup"))) {
  $l = $W.CreateShortcut((Join-Path $dest "Mon Studio.lnk"))
  $l.TargetPath = $Cible; $l.Arguments = $Arguments; $l.WorkingDirectory = $Studio
  $l.IconLocation = "$env:SystemRoot\System32\shell32.dll,115"; $l.Save()
}
Ok "icone 'Mon Studio' sur le Bureau (et demarrage automatique avec Windows)"

Etape 7 "Connexion Tailscale (pour le telephone)"
function Run-WithLink($argList, $msg) {
  # Lance tailscale, ouvre dans le navigateur le lien de connexion/activation s'il en affiche un, attend la fin (5 min max).
  $out = Join-Path $env:TEMP "studio_ts.txt"; Remove-Item $out -ErrorAction SilentlyContinue
  $p = Start-Process $Ts -ArgumentList $argList -RedirectStandardOutput $out -RedirectStandardError "$out.err" -WindowStyle Hidden -PassThru
  $opened = $false
  for ($i = 0; $i -lt 300 -and -not $p.HasExited; $i++) {
    Start-Sleep 1
    $txt = (Get-Content $out, "$out.err" -Raw -ErrorAction SilentlyContinue) -join " "
    if (-not $opened -and $txt -match "(https://login\.tailscale\.com/\S+)") { Write-Host "   $msg"; Start-Process $Matches[1]; $opened = $true }
  }
  if (-not $p.HasExited) { $p.Kill() }
}
if (Test-Path $Ts) {
  $j = & $Ts status --json 2>$null | ConvertFrom-Json
  if (-not $j -or $j.BackendState -ne "Running") {
    Run-WithLink @("up") "Une page s'ouvre : connectez-vous (Google, Microsoft ou Apple), puis revenez ici."
  }
  Run-WithLink @("serve", "--bg", "8765") "Une page s'ouvre : cliquez sur 'Enable' pour activer HTTPS, puis revenez ici."
  $dns = ((& $Ts status --json | ConvertFrom-Json).Self.DNSName).TrimEnd(".")
  if ($dns) { Ok "Adresse pour le telephone : https://$dns" } else { Ko "Tailscale non connecte : relancez l'installateur plus tard pour le telephone." }
}

Write-Host ""
Write-Host "  INSTALLATION TERMINEE" -ForegroundColor Green
Write-Host "  Le studio s'ouvre dans votre navigateur. Ensuite : double-cliquez 'Mon Studio' sur le Bureau."
Start-Process powershell.exe -ArgumentList $Arguments -WindowStyle Hidden
