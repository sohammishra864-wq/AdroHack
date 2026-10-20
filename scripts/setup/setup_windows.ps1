# ClaimShield - one-shot setup for the DEMO laptop (Windows 10/11, PowerShell 5.1+).
# Run from the repo root:
#   powershell -ExecutionPolicy Bypass -File scripts\setup\setup_windows.ps1
# Flags: -SkipSystem (tools already installed)  -SkipModels  -SkipBuildTools  -SkipArena
# Needs ~30 GB free (build tools ~7 GB, packages ~5 GB, models ~8 GB) and >= 16 GB RAM.
# Safe to re-run: winget skips what is installed, pip and the model download are cached.
param([switch]$SkipSystem, [switch]$SkipModels, [switch]$SkipBuildTools, [switch]$SkipArena)

function Step($msg) { Write-Host "`n=== $msg" -ForegroundColor Cyan }
function Fail($msg) { Write-Host "FAILED: $msg" -ForegroundColor Red; exit 1 }
$env:PYTHONUTF8 = "1"   # python prints arrows and similar characters; the cp1252 console would crash on them

if (-not (Test-Path "requirements.txt")) { Fail "run this from the repo root" }
$free = [math]::Round((Get-PSDrive -Name (Get-Location).Drive.Name).Free / 1GB)
Write-Host "Free disk on this drive: $free GB"
if ($free -lt 30) { Write-Host "WARNING: under 30 GB free; consider -SkipArena / -SkipBuildTools" -ForegroundColor Yellow }

if (-not $SkipSystem) {
    Step "System tools via winget (IDs: check with 'winget search <name>' if one fails)"
    $pkgs = @("Python.Python.3.11", "Git.Git", "UB-Mannheim.TesseractOCR",
              "oschwartz10612.Poppler", "ezwinports.make")
    foreach ($p in $pkgs) {
        winget install -e --id $p --accept-source-agreements --accept-package-agreements
    }
    if (-not $SkipBuildTools) {
        Step "MSVC C++ Build Tools (insightface has no Windows wheel; ~7 GB, takes a while)"
        winget install -e --id Microsoft.VisualStudio.2022.BuildTools --accept-source-agreements `
            --accept-package-agreements --override "--quiet --wait --norestart --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"
    }
    Step "Tesseract on PATH (winget does not add it)"
    $t = "C:\Program Files\Tesseract-OCR"
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($userPath -notlike "*$t*") { [Environment]::SetEnvironmentVariable("Path", "$userPath;$t", "User") }
    $env:Path += ";$t"
    Write-Host "If pdftoppm is still not found later, add Poppler's 'Library\bin' folder to PATH the same way."
}

Step "Python 3.11 venv in .venv"
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    py -3.11 -m venv .venv
    if ($LASTEXITCODE -ne 0) { Fail "py -3.11 not found - open a NEW terminal after installing Python, then re-run" }
}
$py = ".\.venv\Scripts\python.exe"
& $py -m pip install --upgrade pip
& $py -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { Fail "pip install -r requirements.txt (insightface? -> install the build tools, new terminal, re-run)" }

if (-not $SkipModels) {
    Step "Models (~8 GB; same loaders the app uses)"
    $args_ = @("scripts\setup\download_models.py")
    if ($SkipArena) { $args_ += "--skip-arena" }
    & $py @args_
    if ($LASTEXITCODE -ne 0) { Write-Host "Some model/tool checks failed - see the table above." -ForegroundColor Yellow }
}

Step "Tests"
& $py -m pytest -q
Write-Host "`nNext: set the Bedrock env vars (copy .env.example to .env), then 'make demo'." -ForegroundColor Green
