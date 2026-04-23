resource "random_id" "uploads_suffix" {
  byte_length = 2
}

resource "aws_s3_bucket" "uploads" {
  bucket = "${var.project}-${var.environment}-uploads-${random_id.uploads_suffix.hex}"

  tags = {
    Project     = var.project
    Environment = var.environment
    Purpose     = "proof-uploads"
  }
}

resource "aws_s3_bucket_public_access_block" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "uploads" {
  bucket = aws_s3_bucket.uploads.id
  versioning_configuration {
    status = "Enabled"
  }
}
