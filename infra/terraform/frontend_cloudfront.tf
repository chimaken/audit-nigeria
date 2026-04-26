# Static Next.js export (`frontend/out`) → private S3 + CloudFront (OAC).

check "frontend_static_export_exists" {
  assert {
    condition = !var.frontend_cloudfront_enabled || fileexists(
      abspath("${path.module}/${var.frontend_static_out_dir}/index.html"),
    )
    error_message = "With frontend_cloudfront_enabled, run a static export first: cd frontend; $env:STATIC_EXPORT='1'; $env:NEXT_PUBLIC_API_URL='https://<apprunner-host>'; npm run build — then terraform apply."
  }
}

resource "random_id" "frontend_suffix" {
  count       = var.frontend_cloudfront_enabled ? 1 : 0
  byte_length = 2
}

locals {
  frontend_out_abs = abspath("${path.module}/${var.frontend_static_out_dir}")
  frontend_fileset = var.frontend_cloudfront_enabled ? toset(fileset(local.frontend_out_abs, "**")) : toset([])
}

resource "aws_s3_bucket" "frontend" {
  count  = var.frontend_cloudfront_enabled ? 1 : 0
  bucket = "${var.project}-${var.environment}-frontend-${random_id.frontend_suffix[0].hex}"

  tags = {
    Project     = var.project
    Environment = var.environment
    Purpose     = "next-static-export"
  }
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  count  = var.frontend_cloudfront_enabled ? 1 : 0
  bucket = aws_s3_bucket.frontend[0].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "frontend" {
  count  = var.frontend_cloudfront_enabled ? 1 : 0
  bucket = aws_s3_bucket.frontend[0].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

data "aws_cloudfront_cache_policy" "caching_optimized" {
  count = var.frontend_cloudfront_enabled ? 1 : 0
  name  = "Managed-CachingOptimized"
}

resource "aws_cloudfront_origin_access_control" "frontend" {
  count                             = var.frontend_cloudfront_enabled ? 1 : 0
  name                              = substr("${var.project}-${var.environment}-frontend-oac", 0, 64)
  description                       = "OAC for ${var.project} ${var.environment} dashboard bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_function" "next_static_uri" {
  count   = var.frontend_cloudfront_enabled ? 1 : 0
  name    = substr("${var.project}-${var.environment}-next-static-uri", 0, 64)
  runtime = "cloudfront-js-1.0"
  comment = "Rewrite /path and /path/ to /path/index.html for Next export (trailingSlash)"
  publish = true
  code    = file("${path.module}/cloudfront_next_static_viewer_request.js")
}

resource "aws_s3_object" "frontend" {
  for_each = local.frontend_fileset

  bucket = aws_s3_bucket.frontend[0].id
  key    = each.key
  source = "${local.frontend_out_abs}/${each.key}"
  etag   = filemd5("${local.frontend_out_abs}/${each.key}")

  content_type = (
    endswith(lower(each.key), ".html") ? "text/html; charset=utf-8" :
    endswith(lower(each.key), ".css") ? "text/css; charset=utf-8" :
    endswith(lower(each.key), ".js") ? "application/javascript; charset=utf-8" :
    endswith(lower(each.key), ".json") ? "application/json; charset=utf-8" :
    endswith(lower(each.key), ".map") ? "application/json; charset=utf-8" :
    endswith(lower(each.key), ".txt") ? "text/plain; charset=utf-8" :
    endswith(lower(each.key), ".svg") ? "image/svg+xml" :
    endswith(lower(each.key), ".png") ? "image/png" :
    endswith(lower(each.key), ".jpg") ? "image/jpeg" :
    endswith(lower(each.key), ".jpeg") ? "image/jpeg" :
    endswith(lower(each.key), ".ico") ? "image/x-icon" :
    endswith(lower(each.key), ".webp") ? "image/webp" :
    endswith(lower(each.key), ".woff2") ? "font/woff2" :
    endswith(lower(each.key), ".woff") ? "font/woff" :
    "application/octet-stream"
  )

  cache_control = (
    startswith(each.key, "_next/static/") ? "public, max-age=31536000, immutable" :
    endswith(lower(each.key), ".html") ? "public, max-age=0, must-revalidate" :
    null
  )
}

resource "aws_cloudfront_distribution" "frontend" {
  count = var.frontend_cloudfront_enabled ? 1 : 0

  enabled             = true
  is_ipv6_enabled     = true
  comment             = "${var.project} ${var.environment} dashboard"
  default_root_object = "index.html"
  price_class         = "PriceClass_100"

  origin {
    domain_name              = aws_s3_bucket.frontend[0].bucket_regional_domain_name
    origin_id                = "s3-frontend"
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend[0].id
  }

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "s3-frontend"
    compress               = true
    viewer_protocol_policy = "redirect-to-https"
    cache_policy_id        = data.aws_cloudfront_cache_policy.caching_optimized[0].id

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.next_static_uri[0].arn
    }
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  depends_on = [aws_s3_object.frontend]

  tags = {
    Project     = var.project
    Environment = var.environment
  }
}

data "aws_iam_policy_document" "frontend_bucket_cloudfront" {
  count = var.frontend_cloudfront_enabled ? 1 : 0

  statement {
    sid    = "AllowCloudFrontRead"
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.frontend[0].arn}/*"]
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.frontend[0].arn]
    }
  }
}

resource "aws_s3_bucket_policy" "frontend" {
  count  = var.frontend_cloudfront_enabled ? 1 : 0
  bucket = aws_s3_bucket.frontend[0].id
  policy = data.aws_iam_policy_document.frontend_bucket_cloudfront[0].json

  depends_on = [aws_cloudfront_distribution.frontend]
}
