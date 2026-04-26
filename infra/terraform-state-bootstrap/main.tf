# One-time bootstrap: S3 + DynamoDB for the *main* Terraform stack remote backend.
# Uses local state for this tiny root module only. After apply, copy outputs into GitHub Secrets
# TF_STATE_BUCKET + TF_STATE_LOCK_TABLE and configure the main stack (see infra/README.md).
#
# From this directory: terraform init -input=false
#   then: terraform apply -input=false (with terraform.tfvars from terraform.tfvars.example, or -var flags).

data "aws_caller_identity" "current" {}

locals {
  bucket_name = substr("${var.project}-${var.environment}-tfstate-${data.aws_caller_identity.current.account_id}", 0, 63)
  lock_name   = substr("${var.project}-${var.environment}-terraform-locks", 0, 255)
}

resource "aws_s3_bucket" "terraform_state" {
  bucket = local.bucket_name

  tags = {
    Project     = var.project
    Environment = var.environment
    Purpose     = "terraform-remote-state"
  }
}

resource "aws_s3_bucket_versioning" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "terraform_state" {
  bucket                  = aws_s3_bucket.terraform_state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_dynamodb_table" "terraform_lock" {
  name         = local.lock_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  tags = {
    Project     = var.project
    Environment = var.environment
    Purpose     = "terraform-state-lock"
  }
}
