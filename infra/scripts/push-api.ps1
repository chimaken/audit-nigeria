<#.SYNOPSIS
  Build backend/Dockerfile and push to the App Runner ECR repository (same image as Terraform image_identifier).

.EXAMPLE
  cd infra\terraform
  ..\scripts\push-api.ps1 -RepositoryUrl (terraform output -raw ecr_repository_url) -Tag manual-1 -Region eu-west-1

  # After push, if apprunner_auto_deployments_enabled is false in Terraform, bump apprunner_image_tag (or redeploy in console).
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
  docker build `
    --platform linux/amd64 `
    --provenance=false `
    --sbom=false `
    -f backend/Dockerfile `
    -t audit-nigeria-api:local `
    .
  if ($LASTEXITCODE -ne 0) {
    throw "docker build failed (exit $LASTEXITCODE); need Docker 23+ for --provenance/--sbom or upgrade Docker Desktop"
  }
  $profileArg = ""
  if (-not [string]::IsNullOrWhiteSpace($AwsProfile)) {
    $profileArg = " --profile $($AwsProfile.Trim())"
  }
  $loginCmd = "aws ecr get-login-password --region $Region$profileArg | docker login --username AWS --password-stdin $registry"
  cmd /c $loginCmd
  if ($LASTEXITCODE -ne 0) {
    throw "docker login failed (exit $LASTEXITCODE). Check aws sts get-caller-identity and optional -AwsProfile."
  }
  docker tag audit-nigeria-api:local $remote
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
Write-Host "If App Runner auto_deployments_enabled is false, change apprunner_image_tag in terraform.tfvars and run terraform apply, or start a deployment in the App Runner console."
