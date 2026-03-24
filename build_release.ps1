$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

python -m PyInstaller --noconfirm --clean AutoGamePlay.spec

Write-Host ""
Write-Host "Build complete."
Write-Host "Output: $root\dist\AutoGamePlay\AutoGamePlay.exe"
