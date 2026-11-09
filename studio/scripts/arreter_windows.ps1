# Arrete Mon Studio.
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*-m serveur*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Write-Host "Studio arrete."
