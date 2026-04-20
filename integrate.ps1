param(
    [switch]$BuildAdmin = $true,
    [switch]$CopyConsumer = $true,
    [switch]$SeedDatabase = $false
)

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ConsumerSource = Join-Path $RepoRoot 'consumer'
$ConsumerTarget = Join-Path $RepoRoot 'backend\server\static\consumer'
$AdminDir = Join-Path $RepoRoot 'geo-admin'
$BackendServerDir = Join-Path $RepoRoot 'backend\server'
$DatabaseScript = Join-Path $RepoRoot 'backend\database\build_mock_database.py'
$MediaImportScript = Join-Path $RepoRoot 'backend\database\import_product_media.py'
$DatabasePath = Join-Path $RepoRoot 'backend\database\android_backend.db'

Write-Host "Repo root: $RepoRoot"

if ($CopyConsumer) {
    Write-Host "Sync consumer assets -> backend/server/static/consumer"
    New-Item -ItemType Directory -Force -Path $ConsumerTarget | Out-Null
    Copy-Item (Join-Path $ConsumerSource '*') $ConsumerTarget -Force
}

if ($BuildAdmin) {
    Write-Host "Build geo-admin -> backend/server/static/admin-vue"
    Push-Location $AdminDir
    try {
        npm.cmd run build
    } finally {
        Pop-Location
    }
}

if ($SeedDatabase) {
    Write-Host "Seed demo database"
    Push-Location $BackendServerDir
    try {
        python ..\database\build_mock_database.py
        python ..\database\import_product_media.py
    } finally {
        Pop-Location
    }
} elseif (Test-Path $DatabasePath) {
    Write-Host "Refresh product media import"
    Push-Location $BackendServerDir
    try {
        python ..\database\import_product_media.py
    } finally {
        Pop-Location
    }
}

Write-Host "Integration completed."
