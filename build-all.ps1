# ======================================
# One-click build script (ASCII-safe for Windows PowerShell 5.1)
# ======================================

$ErrorActionPreference = 'Stop'
$startTime = Get-Date

Write-Host '========================================' -ForegroundColor Cyan
Write-Host '  EasyTuner build (backend + frontend)' -ForegroundColor Cyan
Write-Host '========================================' -ForegroundColor Cyan
Write-Host ''

# Paths
$rootDir    = $PSScriptRoot
$venvPath   = Join-Path $rootDir '.venv\Scripts\Activate.ps1'
$backendDir = Join-Path $rootDir 'backend'
$webDir     = Join-Path $rootDir 'web'

# --------------------------------------
# Step 1: Activate Python venv
# --------------------------------------
Write-Host '[1/3] Activate Python venv...' -ForegroundColor Yellow

if (-not (Test-Path $venvPath)) {
    Write-Host ('ERROR: venv not found: {0}' -f $venvPath) -ForegroundColor Red
    Write-Host "HINT: run 'python -m venv .venv' first." -ForegroundColor Yellow
    exit 1
}

if (-not $env:VIRTUAL_ENV) {
    # Allow running the activation script in this process only
    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -ErrorAction SilentlyContinue | Out-Null
    Write-Host ('  Using: {0}' -f $venvPath) -ForegroundColor Gray
    . $venvPath
}

if (-not $env:VIRTUAL_ENV) {
    Write-Host 'ERROR: venv activation failed (VIRTUAL_ENV missing)' -ForegroundColor Red
    exit 1
}

Write-Host ('OK: venv = {0}' -f $env:VIRTUAL_ENV) -ForegroundColor Green
Write-Host ''

# --------------------------------------
# Step 2: Build backend
# --------------------------------------
Write-Host '[2/3] Build backend (PyInstaller)...' -ForegroundColor Yellow
Set-Location $backendDir

if (Test-Path 'build') { Remove-Item 'build' -Recurse -Force }
if (Test-Path 'dist')  { Remove-Item 'dist'  -Recurse -Force }
if (Test-Path 'EasyTunerBackend.spec') { Remove-Item 'EasyTunerBackend.spec' -Force }

$py = Join-Path $rootDir '.venv\Scripts\python.exe'
Write-Host '  Running PyInstaller...' -ForegroundColor Gray

# Avoid backticks by using an argument array
$piArgs = @(
    '-m','PyInstaller',
    '--noconfirm','--clean',
    '--name','EasyTunerBackend',
    '--onefile','--console',
    '--paths','.',
    '--collect-submodules','app',
    '--collect-submodules','google.protobuf',
    '--hidden-import','google.protobuf.internal',
    'serve.py'
)
& $py @piArgs

if ($LASTEXITCODE -ne 0) {
    Write-Host 'ERROR: backend build failed' -ForegroundColor Red
    exit 1
}

$backendExe = Join-Path $backendDir 'dist\EasyTunerBackend.exe'
if (-not (Test-Path $backendExe)) {
    Write-Host ('ERROR: backend exe not found: {0}' -f $backendExe) -ForegroundColor Red
    exit 1
}

Write-Host ('OK: backend built: {0}' -f $backendExe) -ForegroundColor Green
Write-Host ''

# --------------------------------------
# Step 3: Build frontend
# --------------------------------------
Write-Host '[3/3] Build frontend...' -ForegroundColor Yellow
Set-Location $webDir

Write-Host '  Installing deps...' -ForegroundColor Gray
pnpm install
if ($LASTEXITCODE -ne 0) {
    Write-Host 'ERROR: pnpm install failed' -ForegroundColor Red
    exit 1
}

Write-Host '  Building frontend...' -ForegroundColor Gray
pnpm dist
if ($LASTEXITCODE -ne 0) {
    Write-Host 'ERROR: pnpm dist failed' -ForegroundColor Red
    exit 1
}

$frontendDist = Join-Path $webDir 'dist'
if (-not (Test-Path $frontendDist)) {
    Write-Host ('ERROR: frontend dist not found: {0}' -f $frontendDist) -ForegroundColor Red
    exit 1
}

Write-Host ('OK: frontend built: {0}' -f $frontendDist) -ForegroundColor Green
Write-Host ''

# --------------------------------------
# Done
# --------------------------------------
$endTime  = Get-Date
$duration = $endTime - $startTime

Write-Host '========================================' -ForegroundColor Cyan
Write-Host '  Build completed!' -ForegroundColor Green
Write-Host '========================================' -ForegroundColor Cyan
Write-Host ''
Write-Host 'Backend exe:' -ForegroundColor White
Write-Host ('  {0}' -f $backendExe) -ForegroundColor Gray
Write-Host ''
Write-Host 'Frontend dist:' -ForegroundColor White
Write-Host ('  {0}' -f $frontendDist) -ForegroundColor Gray
Write-Host ''
Write-Host ('Duration: {0} minutes' -f ($duration.TotalMinutes.ToString('0.00'))) -ForegroundColor Cyan
Write-Host ''

# Return to root
Set-Location $rootDir
