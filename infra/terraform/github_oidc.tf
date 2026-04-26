# One OIDC provider per account for GitHub is normal; reference it instead of creating.
data "aws_iam_openid_connect_provider" "github" {
  count = var.github_org != "" && var.github_repo != "" ? 1 : 0
  arn   = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/token.actions.githubusercontent.com"
}

locals {
  github_role_enabled = var.github_org != "" && var.github_repo != ""
  ecr_repos_for_github = concat(
    [aws_ecr_repository.api.arn],
    length(aws_ecr_repository.upload_worker) > 0 ? [aws_ecr_repository.upload_worker[0].arn] : []
  )
}

data "aws_iam_policy_document" "github_trust" {
  count = var.github_org != "" && var.github_repo != "" ? 1 : 0

  statement {
    effect = "Allow"
    actions = [
      "sts:AssumeRoleWithWebIdentity",
    ]
    principals {
      type        = "Federated"
      identifiers = [data.aws_iam_openid_connect_provider.github[0].arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_org}/${var.github_repo}:${var.github_branch_ref}"]
    }
  }
}

resource "aws_iam_role" "github_ecr_push" {
  count = var.github_org != "" && var.github_repo != "" ? 1 : 0

  name               = substr("${var.project}-${var.environment}-github-ecr", 0, 64)
  assume_role_policy = data.aws_iam_policy_document.github_trust[0].json

  tags = {
    Project     = var.project
    Environment = var.environment
  }
}

data "aws_iam_policy_document" "github_ecr_push" {
  statement {
    sid    = "EcrAuth"
    effect = "Allow"
    actions = [
      "ecr:GetAuthorizationToken",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "EcrPushPull"
    effect = "Allow"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:CompleteLayerUpload",
      "ecr:GetDownloadUrlForLayer",
      "ecr:InitiateLayerUpload",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
    ]
    resources = local.ecr_repos_for_github
  }
}

data "aws_iam_policy_document" "github_apprunner_deploy" {
  count = local.github_role_enabled && var.apprunner_enabled ? 1 : 0

  statement {
    sid    = "AppRunnerReadWrite"
    effect = "Allow"
    actions = [
      "apprunner:DescribeService",
      "apprunner:ListOperations",
      "apprunner:DescribeOperation",
      "apprunner:UpdateService",
    ]
    resources = [aws_apprunner_service.api[0].arn]
  }
}

data "aws_iam_policy_document" "github_frontend_deploy" {
  count = local.github_role_enabled && var.frontend_cloudfront_enabled ? 1 : 0

  # ListBucket: bucket ARN only. GetObject/PutObject/DeleteObject: `bucket/*` (S3 action/resource pairs).
  statement {
    sid       = "FrontendS3List"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.frontend[0].arn]
  }

  statement {
    sid    = "FrontendS3Objects"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    resources = ["${aws_s3_bucket.frontend[0].arn}/*"]
  }

  statement {
    sid    = "CloudFrontInvalidate"
    effect = "Allow"
    actions = [
      "cloudfront:CreateInvalidation",
    ]
    resources = [aws_cloudfront_distribution.frontend[0].arn]
  }
}

data "aws_iam_policy_document" "github_upload_worker_lambda" {
  count = local.github_role_enabled && length(aws_lambda_function.upload_worker) > 0 ? 1 : 0

  statement {
    sid    = "LambdaUpdateImage"
    effect = "Allow"
    actions = [
      "lambda:UpdateFunctionCode",
      "lambda:GetFunction",
    ]
    resources = [aws_lambda_function.upload_worker[0].arn]
  }
}

resource "aws_iam_role_policy" "github_ecr_push" {
  count = var.github_org != "" && var.github_repo != "" ? 1 : 0

  name   = "ecr-and-uploads"
  role   = aws_iam_role.github_ecr_push[0].id
  policy = data.aws_iam_policy_document.github_ecr_push.json
}

resource "aws_iam_role_policy" "github_apprunner_deploy" {
  count = local.github_role_enabled && var.apprunner_enabled ? 1 : 0

  name   = "apprunner-deploy"
  role   = aws_iam_role.github_ecr_push[0].id
  policy = data.aws_iam_policy_document.github_apprunner_deploy[0].json
}

resource "aws_iam_role_policy" "github_frontend_deploy" {
  count = local.github_role_enabled && var.frontend_cloudfront_enabled ? 1 : 0

  name   = "frontend-s3-cloudfront"
  role   = aws_iam_role.github_ecr_push[0].id
  policy = data.aws_iam_policy_document.github_frontend_deploy[0].json
}

resource "aws_iam_role_policy" "github_upload_worker_lambda" {
  count = local.github_role_enabled && length(aws_lambda_function.upload_worker) > 0 ? 1 : 0

  name   = "upload-worker-lambda"
  role   = aws_iam_role.github_ecr_push[0].id
  policy = data.aws_iam_policy_document.github_upload_worker_lambda[0].json
}
