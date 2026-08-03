#Requires -Version 5.1
<#
.SYNOPSIS
  Install ComfyUI for Mimir local image generation.

.USAGE
  powershell -ExecutionPolicy Bypass -File scripts/setup_comfyui.ps1
  powershell -ExecutionPolicy Bypass -File scripts/setup_comfyui.ps1 -WithModel
#>
param(
    [switch]$WithModel
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Tools = Join-Path $Root "tools"
$ComfyDir = Join-Path $Tools "ComfyUI"
$Checkpoints = Join-Path $ComfyDir "models\checkpoints"
$Python = Join-Path $Root "venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    $Python = Join-Path $Root "backend\.venv\Scripts\python.exe"
}
if (-not (Test-Path $Python)) {
    Write-Host "ERROR: No Mimir venv found. Run: python -m venv venv && venv\Scripts\pip install -r backend\requirements.txt"
    exit 1
}

Write-Host "=== Mimir ComfyUI Setup ===" -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $Tools | Out-Null

if (-not (Test-Path (Join-Path $ComfyDir "main.py"))) {
    Write-Host "Cloning ComfyUI into tools/ComfyUI ..."
    git clone https://github.com/comfyanonymous/ComfyUI.git $ComfyDir
} else {
    Write-Host "ComfyUI already cloned."
}

Write-Host "Installing ComfyUI Python dependencies (may take several minutes) ..."
& $Python -m pip install --upgrade pip
& $Python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
& $Python -m pip install -r (Join-Path $ComfyDir "requirements.txt")

New-Item -ItemType Directory -Force -Path $Checkpoints | Out-Null

$DefaultModel = "v1-5-pruned-emaonly.safetensors"
$ModelPath = Join-Path $Checkpoints $DefaultModel

if (-not (Test-Path $ModelPath)) {
    if ($WithModel) {
        Write-Host "Downloading SD 1.5 checkpoint (~4 GB). This takes a while ..."
        $Url = "https://huggingface.co/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.safetensors"
        Invoke-WebRequest -Uri $Url -OutFile $ModelPath -UseBasicParsing
        Write-Host "Model saved to $ModelPath"
    } else {
        Write-Host ""
        Write-Host "No checkpoint found in models/checkpoints/" -ForegroundColor Yellow
        Write-Host "Download a .safetensors model manually, OR re-run with -WithModel:"
        Write-Host "  powershell -ExecutionPolicy Bypass -File scripts/setup_comfyui.ps1 -WithModel"
        Write-Host ""
        Write-Host "Place any checkpoint in:" -ForegroundColor Yellow
        Write-Host "  $Checkpoints"
    }
} else {
    Write-Host "Checkpoint found: $DefaultModel"
}

# Write mimir.env if missing
$EnvFile = Join-Path $Root "mimir.env"
if (-not (Test-Path $EnvFile)) {
    Copy-Item (Join-Path $Root "mimir.env.example") $EnvFile
    Write-Host "Created mimir.env with MIMIR_IMAGE_PROVIDER=comfyui"
} else {
    Write-Host "mimir.env already exists - ensure it contains:"
    Write-Host "  MIMIR_IMAGE_PROVIDER=comfyui"
    Write-Host "  MIMIR_COMFYUI_URL=http://127.0.0.1:8188"
}

Write-Host ""
Write-Host "=== Setup complete ===" -ForegroundColor Green
Write-Host "Start ComfyUI:"
Write-Host "  powershell -ExecutionPolicy Bypass -File scripts/start_comfyui.ps1"
Write-Host ""
Write-Host "Then restart Mimir (python run_platform.py) so it picks up mimir.env"
