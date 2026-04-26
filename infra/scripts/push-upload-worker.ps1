<#.SYNOPSIS
  Build backend/Dockerfile.lambda and push to ECR (required before Terraform can create the upload-worker Lambda).

.EXAMPLE
  From repo root (reads upload_worker_ecr_url from infra/terraform state):
  .\infra\scripts\push-upload-worker.ps1 -Tag manual-1 -Region eu-west-1

.EXAMPLE
  Explicit URL:
  .\infra\scripts\push-upload-worker.ps1 -RepositoryUrl "123456789012.dkr.ecr.eu-west-1.amazonaws.com/myorg/prod/upload-worker" -Tag manual-1
#>
param(
  [string] $RepositoryUrl = "",
  [string] $Tag = "latest",
  [string] $Region = "eu-west-1",
  [string] $RepoRoot = "",
  [string] $TerraformDir = "",
  [string] $AwsProfile = ""
)

$ErrorActionPreference = "Stop"
if (-not $RepoRoot) {
  $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}

if ([string]::IsNullOrWhiteSpace($RepositoryUrl)) {
  if (-not $TerraformDir) {
    $TerraformDir = (Resolve-Path (Join-Path $PSScriptRoot "..\terraform")).Path
  }
  else {
    $TerraformDir = (Resolve-Path $TerraformDir).Path
  }
  # Avoid terraform -chdir= on Windows (paths with C:\ often break the Go flag parser).
  Push-Location $TerraformDir
  try {
    $raw = terraform output -raw upload_worker_ecr_url
    if ($LASTEXITCODE -ne 0) {
      throw "terraform output failed (exit $LASTEXITCODE). Run terraform init in $TerraformDir or pass -RepositoryUrl."
    }
    $RepositoryUrl = if ($null -eq $raw) { "" } else { $raw.Trim() }
  }
  finally {
    Pop-Location
  }
  if ([string]::IsNullOrWhiteSpace($RepositoryUrl)) {
    throw "upload_worker_ecr_url is empty. Apply Terraform with the async upload pipeline enabled, or pass -RepositoryUrl explicitly."
  }
}

$slash = $RepositoryUrl.IndexOf("/")
if ($slash -lt 0) {
  throw "RepositoryUrl must look like 123456789.dkr.ecr.region.amazonaws.com/repo/name (no tag)."
}
$registry = $RepositoryUrl.Substring(0, $slash)
$remote = "${RepositoryUrl}:${Tag}"

Push-Location $RepoRoot
try {
  # Lambda rejects BuildKit-only manifest lists / OCI attestations ("media type ... not supported").
  # Single linux/amd64 image, no provenance/SBOM side manifests (Docker Desktop 23+).
  docker build `
    --platform linux/amd64 `
    --provenance=false `
    --sbom=false `
    -f backend/Dockerfile.lambda `
    -t upload-worker:local `
    .
  if ($LASTEXITCODE -ne 0) {
    throw "docker build failed (exit $LASTEXITCODE); need Docker 23+ for --provenance/--sbom or upgrade Docker Desktop"
  }
  # PowerShell piping a string into docker --password-stdin often breaks ECR (HTTP 400).
  # Run the pipe under cmd.exe so the token matches Linux/macOS behavior.
  $profileArg = ""
  if (-not [string]::IsNullOrWhiteSpace($AwsProfile)) {
    $profileArg = " --profile $($AwsProfile.Trim())"
  }
  $loginCmd = "aws ecr get-login-password --region $Region$profileArg | docker login --username AWS --password-stdin $registry"
  cmd /c $loginCmd
  if ($LASTEXITCODE -ne 0) {
    throw "docker login failed (exit $LASTEXITCODE). Try cmd pipe (fixed in script), aws sts get-caller-identity, and optional -AwsProfile."
  }
  docker tag upload-worker:local $remote
  if ($LASTEXITCODE -ne 0) {
    throw "docker tag failed (exit $LASTEXITCODE)"
  }
  docker push $remote
  if ($LASTEXITCODE -ne 0) {
    throw "docker push failed (exit $LASTEXITCODE)"
  }
}
finally {
  Pop-Location
}

Write-Host "Pushed $remote"
