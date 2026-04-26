#Requires -Version 5.1
# Single deploy entry: -Mode Infra|Backend|Frontend|App. See infra/README.md.
[CmdletBinding()]
param(
    [ValidateSet("Infra", "Backend", "Frontend", "App")]
    [string]$Mode = "App",
    [switch]$ApplyTerraform,
    [switch]$SkipPush,
    [switch]$SkipFrontendTerraform,
    [switch]$InfraInitOnly,
    [string]$ImageTag = "",
    [string]$ApiUrl = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Get-Item $PSScriptRoot).Parent.Parent.FullName
$TfDir = Join-Path $RepoRoot "infra\terraform"
$TfVars = Join-Path $TfDir "terraform.tfvars"
$FrontendDir = Join-Path $RepoRoot "frontend"

function Get-DefaultImageTag {
    try {
        Push-Location $RepoRoot
        $sha = (& git rev-parse --short HEAD 2>$null)
        Pop-Location
        if ($LASTEXITCODE -eq 0 -and $sha) { return $sha.Trim() }
    }
    catch { }
    return ("manual-" + (Get-Date -Format "yyyyMMddHHmmss"))
}

function Get-EcrRegionFromRepositoryUri {
    param([Parameter(Mandatory)][string]$RepositoryUri)
    $hostPart = ($RepositoryUri -split "/")[0]
    if ($hostPart -match '\.dkr\.ecr\.([a-z0-9-]+)\.amazonaws\.com') {
        return $Matches[1]
    }
    return $null
}

function Invoke-Infra {
    if (-not (Test-Path $TfVars)) {
        Write-Error "Missing $TfVars - copy terraform.tfvars.example to terraform.tfvars and edit."
    }
    Write-Host "terraform init ..." -ForegroundColor Cyan
    Push-Location $TfDir
    try {
        & terraform init
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        if ($InfraInitOnly) {
            Write-Host "InfraInitOnly: run terraform apply when ready." -ForegroundColor Yellow
            return
        }
        Write-Host "terraform apply -auto-approve ..." -ForegroundColor Cyan
        & terraform apply -auto-approve
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    finally { Pop-Location }
    Write-Host "Infra apply finished. Next: deploy.ps1 -Mode App -ApplyTerraform (after API/frontend work)." -ForegroundColor Green
}

function Invoke-Backend {
    $tag = if ($ImageTag) { $ImageTag } else { Get-DefaultImageTag }

    $ecrUri = $env:ECR_REPOSITORY_URI
    if (-not $ecrUri) {
        Push-Location $TfDir
        try {
            $ecrUri = (& terraform output -raw ecr_repository_url 2>$null)
        }
        finally { Pop-Location }
    }
    if (-not $ecrUri) {
        Write-Error "Set ECR_REPOSITORY_URI or run Terraform so ecr_repository_url exists."
    }

    $fromUri = Get-EcrRegionFromRepositoryUri $ecrUri
    $region = if ($fromUri) { $fromUri }
    elseif ($env:AWS_REGION) { $env:AWS_REGION }
    elseif ($env:AWS_DEFAULT_REGION) { $env:AWS_DEFAULT_REGION }
    else { "eu-west-1" }
    $registry = ($ecrUri -split "/")[0]

    Write-Host "Building image ${ecrUri}:${tag} ..." -ForegroundColor Cyan
    Push-Location $RepoRoot
    try {
        & docker build -f backend/Dockerfile -t "${ecrUri}:${tag}" .
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    finally { Pop-Location }

    if (-not $SkipPush) {
        Write-Host "Logging in to ECR ($registry) (region $region) ..." -ForegroundColor Cyan
        # PS 5.1 piping aws → docker corrupts stdin; ECR then returns 400. Run the pipe in cmd.
        & cmd.exe /c "aws ecr get-login-password --region $region | docker login --username AWS --password-stdin $registry"
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        Write-Host "Pushing ${ecrUri}:${tag} ..." -ForegroundColor Cyan
        & docker push "${ecrUri}:${tag}"
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        Write-Host "Pushed OK." -ForegroundColor Green
    }

    if ($ApplyTerraform) {
        Write-Host "Applying Terraform with apprunner_image_tag=$tag ..." -ForegroundColor Cyan
        Push-Location $TfDir
        try {
            & terraform apply -auto-approve -var "apprunner_image_tag=$tag"
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        }
        finally { Pop-Location }
        Write-Host "Terraform apply (App Runner tag) finished." -ForegroundColor Green
    }
    else {
        Write-Host "Tip: .\scripts\deploy\deploy.ps1 -Mode Backend -ImageTag '$tag' -ApplyTerraform" -ForegroundColor Yellow
    }
}

function Invoke-Frontend {
    $url = $ApiUrl
    if (-not $url) {
        $raw = $null
        Push-Location $TfDir
        try {
            $raw = (& terraform output -raw apprunner_public_url 2>$null)
        }
        finally { Pop-Location }
        if ($raw -and $raw.Trim() -ne "" -and $raw.Trim() -ne "null") {
            $url = $raw.Trim()
        }
    }
    if (-not $url) {
        Write-Error "Pass -ApiUrl https://... or enable App Runner so apprunner_public_url exists."
    }

    $outIndex = Join-Path $FrontendDir "out\index.html"
    $apiDisplay = $url.TrimEnd("/")
    Write-Host "Building static frontend (NEXT_PUBLIC_API_URL=$apiDisplay) ..." -ForegroundColor Cyan
    Push-Location $FrontendDir
    try {
        $env:STATIC_EXPORT = "1"
        $env:NEXT_PUBLIC_API_URL = $url.TrimEnd("/")
        & npm run build:static
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    finally {
        Remove-Item Env:\STATIC_EXPORT -ErrorAction SilentlyContinue
        Remove-Item Env:\NEXT_PUBLIC_API_URL -ErrorAction SilentlyContinue
        Pop-Location
    }

    if (-not (Test-Path $outIndex)) {
        Write-Error "Expected $outIndex after build."
    }

    if (-not $SkipFrontendTerraform) {
        Write-Host "Applying Terraform (S3 / CloudFront) ..." -ForegroundColor Cyan
        Push-Location $TfDir
        try {
            & terraform apply -auto-approve
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        }
        finally { Pop-Location }
        Write-Host "Frontend deploy finished." -ForegroundColor Green
    }
    else {
        Write-Host "SkipFrontendTerraform: run terraform apply from infra/terraform." -ForegroundColor Yellow
    }
}

switch ($Mode) {
    "Infra" { Invoke-Infra }
    "Backend" { Invoke-Backend }
    "Frontend" { Invoke-Frontend }
    "App" {
        Invoke-Backend
        Invoke-Frontend
    }
}

Write-Host "deploy.ps1 -Mode $Mode done." -ForegroundColor Green
