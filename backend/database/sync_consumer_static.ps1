$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))
$source = Join-Path $repoRoot 'consumer'
$target = Join-Path $repoRoot 'backend\server\static\consumer'

New-Item -ItemType Directory -Force -Path $target | Out-Null
Copy-Item (Join-Path $source '*') $target -Force
Write-Host "Synced consumer assets to $target"
