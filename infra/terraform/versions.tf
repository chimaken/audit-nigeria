terraform {
  required_version = ">= 1.5.0"

  backend "s3" {}

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    # Keep random below 3.7 to avoid noisy in-place password resource updates in plans.
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
