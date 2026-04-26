terraform {
  required_version = ">= 1.5.0"

  # Remote state (S3 + DynamoDB). Do not run plain `terraform init` here — it will prompt interactively.
  # Use: `terraform init -backend-config=backend.hcl` (PowerShell: `terraform init "-backend-config=backend.hcl"`), or
  # `terraform init -backend=false` for fmt/validate only, or CI passes -backend-config (see deploy-main.yml).
  backend "s3" {}

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    # Stay on 3.6.x: 3.7+ added random_password schema fields that can force noisy in-place updates in CI.
    random = {
      source  = "hashicorp/random"
      version = ">= 3.6.0, < 3.7.0"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
  }
}
