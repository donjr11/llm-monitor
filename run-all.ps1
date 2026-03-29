# ============================================================
#  run-all.ps1 — LLM Monitor Complete Stack Launcher
#  Starts: FastAPI backend · Next.js dashboard · n8n automation
# ============================================================

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

# ── Helpers ─────────────────────────────────────────────────
function Write-Header {
    Clear-Host
    Write-Host ""
    Write-Host "  ███████╗██████╗ ██╗███╗   ██╗███████╗ ██████╗ ███╗   ██╗" -ForegroundColor Cyan
    Write-Host "  ██╔════╝██╔══██╗██║████╗  ██║██╔════╝██╔═══██╗████╗  ██║" -ForegroundColor Cyan
    Write-Host "  █████╗  ██████╔╝██║██╔██╗ ██║█████╗  ██║   ██║██╔██╗ ██║" -ForegroundColor DarkCyan
    Write-Host "  ██╔══╝  ██╔═══╝ ██║██║╚██╗██║██╔══╝  ██║   ██║██║╚██╗██║" -ForegroundColor DarkCyan
    Write-Host "  ███████╗██║     ██║██║ ╚████║███████╗╚██████╔╝██║ ╚████║" -ForegroundColor Blue
    Write-Host "  ╚══════╝╚═╝     ╚═╝╚═╝  ╚═══╝╚══════╝ ╚═════╝ ╚═╝  ╚═══╝" -ForegroundColor Blue
    Write-Host ""
    Write-Host "  LLM Monitor  —  Full Stack Launcher" -ForegroundColor White
    Write-Host "  PFE Challenge 2026  —  ESITH" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  ─────────────────────────────────────────────────────────" -ForegroundColor DarkGray
    Write-Host ""
}

function Write-Step([string]$msg) {
    Write-Host "  ▶  $msg" -ForegroundColor Cyan
}

function Write-OK([string]$msg) {
    Write-Host "  ✓  $msg" -ForegroundColor Green
}

function Write-Warn([string]$msg) {
    Write-Host "  ⚠  $msg" -ForegroundColor Yellow
}

function Write-Err([string]$msg) {
    Write-Host "  ✗  $msg" -ForegroundColor Red
}

# ── Preflight checks ─────────────────────────────────────────
Write-Header

Write-Host "  Checking prerequisites..." -ForegroundColor DarkGray
Write-Host ""

# Python venv
if (-not (Test-Path "$Root\venv\Scripts\python.exe")) {
    Write-Err "Python venv not found at .\venv\"
    Write-Host ""
    Write-Host "  Fix: python -m venv venv" -ForegroundColor Yellow
    Write-Host "       venv\Scripts\pip install -r requirements.txt" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "  Press Enter to exit"
    exit 1
}
Write-OK "Python venv found"

# Next.js node_modules
if (-not (Test-Path "$Root\next-dashboard\node_modules")) {
    Write-Err "Next.js dependencies not installed"
    Write-Host ""
    Write-Host "  Fix: cd next-dashboard && npm install" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "  Press Enter to exit"
    exit 1
}
Write-OK "Next.js dependencies found"

# npx available
$npxPath = Get-Command npx -ErrorAction SilentlyContinue
if (-not $npxPath) {
    Write-Err "npx not found — Node.js required for n8n"
    Write-Warn "Install Node.js from https://nodejs.org or skip n8n"
    $skipN8n = $true
} else {
    Write-OK "Node.js / npx found"
    $skipN8n = $false
}

Write-Host ""
Write-Host "  ─────────────────────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host ""

# ── 1. FastAPI Backend ───────────────────────────────────────
Write-Step "Launching FastAPI backend  (port 8000)..."

$backendCmd = "& {
    `$Host.UI.RawUI.WindowTitle = 'Backend  |  http://localhost:8000';
    Set-Location '$Root';
    `$env:PYTHONIOENCODING = 'utf-8';
    Write-Host '';
    Write-Host '  EPINEON AI  -  Backend' -ForegroundColor Cyan;
    Write-Host '  http://localhost:8000' -ForegroundColor DarkGray;
    Write-Host '';
    & '.\venv\Scripts\python.exe' -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
}"

Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd
Write-OK "Backend window opened"
Start-Sleep -Seconds 2

# ── 2. Next.js Dashboard ─────────────────────────────────────
Write-Step "Launching Next.js dashboard  (port 3000)..."

$frontendCmd = "& {
    `$Host.UI.RawUI.WindowTitle = 'Dashboard  |  http://localhost:3000';
    Set-Location '$Root\next-dashboard';
    Write-Host '';
    Write-Host '  EPINEON AI  -  Dashboard' -ForegroundColor Cyan;
    Write-Host '  http://localhost:3000' -ForegroundColor DarkGray;
    Write-Host '';
    npm run dev
}"

Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd
Write-OK "Dashboard window opened"
Start-Sleep -Seconds 2

# ── 3. n8n Automation ────────────────────────────────────────
if (-not $skipN8n) {
    Write-Step "Launching n8n automation  (port 5678)..."

    $n8nCmd = "& {
        `$Host.UI.RawUI.WindowTitle = 'n8n  |  http://localhost:5678';
        Set-Location '$Root';
        Write-Host '';
        Write-Host '  EPINEON AI  -  n8n Automation' -ForegroundColor Cyan;
        Write-Host '  http://localhost:5678' -ForegroundColor DarkGray;
        Write-Host '  First launch may take 1-2 minutes...' -ForegroundColor Yellow;
        Write-Host '';
        npx n8n
    }"

    Start-Process powershell -ArgumentList "-NoExit", "-Command", $n8nCmd
    Write-OK "n8n window opened"
} else {
    Write-Warn "n8n skipped (Node.js not found)"
}

# ── Wait & open browsers ─────────────────────────────────────
Write-Host ""
Write-Host "  Waiting for services to initialise..." -ForegroundColor DarkGray
Write-Host ""

$services = @(
    @{ Name = "Backend  "; Url = "http://localhost:8000/docs"; Delay = 5 },
    @{ Name = "Dashboard"; Url = "http://localhost:3000";      Delay = 3 },
    @{ Name = "n8n      "; Url = "http://localhost:5678";      Delay = 3 }
)

foreach ($svc in $services) {
    Start-Sleep -Seconds $svc.Delay
    Write-Host "  Opening $($svc.Name) — $($svc.Url)" -ForegroundColor DarkGray
    Start-Process $svc.Url
}

# ── Summary ──────────────────────────────────────────────────
Write-Host ""
Write-Host "  ─────────────────────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  All services launched successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "  Service       Port   URL" -ForegroundColor White
Write-Host "  ──────────────────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host "  Dashboard     3000   http://localhost:3000" -ForegroundColor Cyan
Write-Host "  Backend API   8000   http://localhost:8000/docs" -ForegroundColor Cyan
if (-not $skipN8n) {
    Write-Host "  n8n           5678   http://localhost:5678" -ForegroundColor Cyan
}
Write-Host ""
Write-Host "  To configure the workflow automation, see N8N-SETUP.md" -ForegroundColor Yellow
Write-Host ""
Write-Host "  ─────────────────────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host ""
Read-Host "  Press Enter to close this launcher"
