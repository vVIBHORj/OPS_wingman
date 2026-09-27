# OpsWingman - Local Dev Environment Setup (PowerShell)
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  OpsWingman Local Dev Environment Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 1. Check for .env file
if (-not (Test-Path ".env")) {
    Write-Host "[1/3] Creating .env from .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "  -> .env created successfully." -ForegroundColor Green
} else {
    Write-Host "[1/3] .env file already exists." -ForegroundColor Green
}

# 2. Check Docker availability
Write-Host "[2/3] Checking Docker engine..." -ForegroundColor Yellow
try {
    $dockerVersion = docker --version
    Write-Host "  -> Docker detected: $dockerVersion" -ForegroundColor Green
    Write-Host "  -> Launching local infrastructure containers..." -ForegroundColor Yellow
    docker compose up -d postgres valkey mailpit langfuse-db langfuse
    Write-Host "  -> Infrastructure services running." -ForegroundColor Green
} catch {
    Write-Host "  -> Docker not running or not found. Please start Docker Desktop." -ForegroundColor Red
}

# 3. Summary
Write-Host "[3/3] Ready for Phase 0 Development!" -ForegroundColor Cyan
Write-Host "  - Backend:  uvicorn backend.main:app --reload --port 8000" -ForegroundColor White
Write-Host "  - Frontend: cd frontend; npm run dev" -ForegroundColor White
Write-Host "  - Mailpit:  http://localhost:8025" -ForegroundColor White
Write-Host "  - Langfuse: http://localhost:3001" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Cyan
