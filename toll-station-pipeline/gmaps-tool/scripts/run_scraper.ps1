param(
  [string]$QueryFile = "queries\smoke_hanoi_haiphong.txt",
  [string]$OutputFile = "data\output\gmaps_results.csv",
  [int]$Depth = 1,
  [int]$Concurrency = 1,
  [string]$ExitOnInactivity = "3m"
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$QueryPath = Resolve-Path (Join-Path $Root $QueryFile)
$OutputPath = Join-Path $Root $OutputFile
$OutputDir = Split-Path $OutputPath -Parent

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

Write-Host "Query file : $QueryPath"
Write-Host "Output file: $OutputPath"
Write-Host "Depth      : $Depth"
Write-Host "Concurrency: $Concurrency"

docker run --rm `
  -v gmaps-playwright-cache:/opt `
  -v "${QueryPath}:/queries.txt:ro" `
  -v "${OutputDir}:/out" `
  gosom/google-maps-scraper `
  -input /queries.txt `
  -results "/out/$(Split-Path $OutputPath -Leaf)" `
  -depth $Depth `
  -c $Concurrency `
  -lang vi `
  -exit-on-inactivity $ExitOnInactivity
