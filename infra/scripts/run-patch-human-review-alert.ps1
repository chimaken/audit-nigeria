# Run backend/sql/patch_human_review_alert.sql against RDS using Docker psql (no local psql required).
# If TcpTestSucceeded is False (connection refused), your laptop cannot reach the RDS public endpoint;
# use the VPC path instead: set upload_worker_admin_patch_token in Terraform, apply, push upload-worker image,
# then:  .\infra\scripts\invoke-patch-human-review-lambda.ps1
# Prereqs: Docker, terraform in PATH, AWS creds if needed for terraform state, RDS reachable from this host.
# Usage (from repo root):  .\infra\scripts\run-patch-human-review-alert.ps1
# Or:  cd infra/terraform; ..\scripts\run-patch-human-review-alert.ps1

$ErrorActionPreference = "Stop"
$tfDir = Join-Path $PSScriptRoot "..\terraform" | Resolve-Path
$sqlDir = Join-Path $PSScriptRoot "..\..\backend\sql" | Resolve-Path
$sqlFile = Join-Path $sqlDir "patch_human_review_alert.sql"

Set-Location $tfDir
$pw = terraform output -raw rds_master_password
$h = terraform output -raw rds_address
$p = (terraform output -raw rds_port).Trim()
$u = terraform output -raw rds_master_username
$d = terraform output -raw rds_database_name

Write-Host "Host=$h port=$p user=$u db=$d"
Write-Host "Testing TCP from Windows (not Docker)..."
$tnc = Test-NetConnection -ComputerName $h -Port ([int]$p) -WarningAction SilentlyContinue
Write-Host "TcpTestSucceeded=$($tnc.TcpTestSucceeded)"

docker run --rm `
    -e "PGPASSWORD=$pw" `
    -v "${sqlDir}:/sql:ro" `
    postgres:16-alpine `
    psql -h "$h" -p "$p" -U "$u" -d "$d" -v ON_ERROR_STOP=1 -f /sql/patch_human_review_alert.sql

Write-Host "Done."
