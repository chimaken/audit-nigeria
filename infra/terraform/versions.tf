terraform {
  required_version = ">= 1.5.0"

  # Remote state (S3 + DynamoDB). Configure with `terraform init -backend-config=...` or CI-generated file.
  # Local-only: `terraform init -backend=false` (e.g. terraform-verify workflow).
  backend "s3" {}

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
  }
}
