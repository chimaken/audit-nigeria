<#.SYNOPSIS
  Build backend/Dockerfile.lambda and push to ECR (required before Terraform can create the upload-worker Lambda).

.EXAMPLE
  cd infra\terraform
  ..\scripts\push-upload-worker.ps1 -RepositoryUrl (terraform output -raw upload_worker_ecr_url) -Tag manual-1 -Region eu-west-1
#>
param(
  [Parameter(Mandatory = $true)]
  [string] $RepositoryUrl,
  [string] $Tag = "latest",
  [string] $Region = "eu-west-1",
  [string] $RepoRoot = "",
  [string] $AwsProfile = ""
)

$ErrorActionPreference = "Stop"
if (-not $RepoRoot) {
  $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
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
