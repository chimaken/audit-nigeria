# Attach this policy to the API runtime role (App Runner instance role, ECS task role, etc.).
data "aws_iam_policy_document" "api_task_uploads" {
  statement {
    sid    = "S3UploadsRW"
    effect = "Allow"
    actions = [
      "s3:PutObject",
      "s3:GetObject",
      "s3:HeadObject",
      "s3:ListBucket",
    ]
    resources = [
      aws_s3_bucket.uploads.arn,
      "${aws_s3_bucket.uploads.arn}/*",
    ]
  }
}

resource "aws_iam_policy" "api_task_uploads" {
  name   = substr("${var.project}-${var.environment}-api-s3-uploads", 0, 128)
  policy = data.aws_iam_policy_document.api_task_uploads.json

  tags = {
    Project     = var.project
    Environment = var.environment
  }
}
