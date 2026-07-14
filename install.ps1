# Install the Common Network node tool (Windows).
#
#   irm https://raw.githubusercontent.com/robot-time/common-network/main/install.ps1 | iex
#
# Installs cloudflared (if missing), fetches join.py, and puts a
# `common-join` command on your PATH. Ollama is checked but not
# auto-installed since it has its own official Windows installer.

$ErrorActionPreference = "Stop"

$Repo = "robot-time/common-network"
$InstallDir = "$env:USERPROFILE\.common-network"
$BinDir = "$InstallDir\bin"
$Raw = "https://raw.githubusercontent.com/$Repo/main"

Write-Host "Installing Common Network node tools..."
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null

# --- python ---
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "Python 3 is required but wasn't found."
    Write-Host "Install it from https://www.python.org/downloads/ (check 'Add python.exe to PATH'), then re-run this installer."
    exit 1
}

# --- cloudflared ---
$cloudflared = Get-Command cloudflared -ErrorAction SilentlyContinue
if (-not $cloudflared -and -not (Test-Path "$BinDir\cloudflared.exe")) {
    Write-Host "Installing cloudflared..."
    $cfUrl = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
    Invoke-WebRequest -Uri $cfUrl -OutFile "$BinDir\cloudflared.exe"
}

# --- ollama ---
$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollama) {
    Write-Host ""
    Write-Host "Ollama isn't installed yet. Download it from https://ollama.com/download,"
    Write-Host "install and open it once (so it's running), then re-run this installer."
    exit 1
}

# --- join.py ---
Write-Host "Downloading the join script..."
Invoke-WebRequest -Uri "$Raw/join/join.py" -OutFile "$InstallDir\join.py"

# --- wrapper command ---
$wrapper = @"
@echo off
set PATH=$BinDir;%PATH%
python "$InstallDir\join.py" %*
"@
Set-Content -Path "$BinDir\common-join.cmd" -Value $wrapper

# --- PATH setup ---
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$BinDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$BinDir", "User")
    Write-Host "Added $BinDir to your PATH."
}

Write-Host ""
Write-Host "Done! Open a new terminal, then run:"
Write-Host ""
Write-Host "    common-join"
Write-Host ""
