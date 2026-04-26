# Run patch_human_review_alert.sql via upload-worker Lambda (VPC path to RDS).
# Prereqs: Terraform has upload_worker_admin_patch_token set, apply done, new worker image pushed (Dockerfile.lambda includes backend/sql).
# Pass token:  $env:LAMBDA_ADMIN_PATCH_TOKEN = "your-token"  (same value as upload_worker_admin_patch_token in terraform.tfvars)
# Usage:       cd infra/terraform; ..\scripts\invoke-patch-human-review-lambda.ps1

$ErrorActionPreference = "Stop"
$token = if ($null -eq $env:LAMBDA_ADMIN_PATCH_TOKEN) { "" } else { $env:LAMBDA_ADMIN_PATCH_TOKEN.Trim() }
if (-not $token) {
    Write-Error "Set LAMBDA_ADMIN_PATCH_TOKEN (must match upload_worker_admin_patch_token in Terraform)."
}

$tfDir = Join-Path $PSScriptRoot "..\terraform" | Resolve-Path
Push-Location $tfDir
try {
    $arn = (terraform output -raw upload_worker_lambda_arn).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $arn) {
        Write-Error "upload_worker_lambda_arn is empty or terraform failed; enable upload worker and apply first."
    }
}
finally {
    Pop-Location
}

$payload = (@{
        action      = "patch_human_review_alert"
        admin_token = $token
    } | ConvertTo-Json -Compress)

if ($arn -notmatch "arn:aws:lambda:([^:]+):") {
    Write-Error "Could not parse region from Lambda ARN: $arn"
}
$region = $Matches[1]

# Windows: --payload file:///C:/... often returns Errno 22. Send JSON on stdin instead (--payload -).
$awsCmd = (Get-Command aws -ErrorAction Stop).Source
if ($awsCmd -match '\.(cmd|ps1)$') {
    $exeCandidate = Join-Path (Split-Path $awsCmd -Parent) "aws.exe"
    if (Test-Path -LiteralPath $exeCandidate) {
        $awsCmd = $exeCandidate
    }
}

$out = Join-Path $env:TEMP "lambda-patch-invoke-$([guid]::NewGuid().ToString('N')).json"
try {
    $payload | & $awsCmd lambda invoke --region $region --function-name $arn --payload - $out
    if ($LASTEXITCODE -ne 0) {
        throw "aws lambda invoke failed (exit $LASTEXITCODE). If stdin failed, ensure AWS CLI v2 and try running from cmd.exe."
    }
    Get-Content -LiteralPath $out -Raw
}
finally {
    Remove-Item -Force -ErrorAction SilentlyContinue -LiteralPath $out
}
