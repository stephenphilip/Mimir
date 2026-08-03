#Requires -Version 5.1
<#
.SYNOPSIS
  Start ComfyUI server for Mimir image generation (port 8188).
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ComfyDir = Join-Path $Root "tools\ComfyUI"
$Python = Join-Path $Root "venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    $Python = Join-Path $Root "backend\.venv\Scripts\python.exe"
}

if (-not (Test-Path (Join-Path $ComfyDir "main.py"))) {
    Write-Host "ComfyUI not installed. Run first:"
    Write-Host "  powershell -ExecutionPolicy Bypass -File scripts/setup_comfyui.ps1"
    exit 1
}

Write-Host "Starting ComfyUI at http://127.0.0.1:8188 ..."
Write-Host "Leave this window open. Press Ctrl+C to stop."
Set-Location $ComfyDir
& $Python main.py --listen 127.0.0.1 --port 8188
