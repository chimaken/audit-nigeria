# Optional: SQS + Lambda container worker for async sheet uploads (presign → browser PUT → complete → worker).

locals {
  # Same VPC + secrets wiring as App Runner; reuses RDS + Terraform-managed DATABASE_URL / OpenRouter secrets.
  upload_worker_enabled = (
    var.upload_async_pipeline_enabled
    && var.rds_enabled
    && var.apprunner_enabled
    && var.rds_create_api_client_security_group
  )
  # CreateFunction requires the container image to already exist in ECR. Use upload_worker_create_lambda=false
  # on the first apply, push backend/Dockerfile.lambda, then set true and apply again (see infra/scripts/push-upload-worker.ps1).
  upload_worker_lambda_enabled = local.upload_worker_enabled && var.upload_worker_create_lambda
}

resource "aws_sqs_queue" "upload_jobs_dlq" {
  count = local.upload_worker_enabled ? 1 : 0

  name                      = substr("${var.project}-${var.environment}-upload-jobs-dlq", 0, 80)
  message_retention_seconds = 1209600

  tags = {
    Project     = var.project
    Environment = var.environment
  }
}

resource "aws_sqs_queue" "upload_jobs" {
  count = local.upload_worker_enabled ? 1 : 0

  name                       = substr("${var.project}-${var.environment}-upload-jobs", 0, 80)
  visibility_timeout_seconds = 960
  message_retention_seconds  = 345600

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.upload_jobs_dlq[0].arn
    maxReceiveCount     = 3
  })

  tags = {
    Project     = var.project
    Environment = var.environment
  }
}

resource "aws_ecr_repository" "upload_worker" {
  count = local.upload_worker_enabled ? 1 : 0

  name                 = "${var.project}/${var.environment}/upload-worker"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Project     = var.project
    Environment = var.environment
  }
}

data "aws_iam_policy_document" "upload_worker_assume" {
  count = local.upload_worker_enabled ? 1 : 0

  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "upload_worker" {
  count = local.upload_worker_enabled ? 1 : 0

  name               = substr("${var.project}-${var.environment}-upload-worker", 0, 64)
  assume_role_policy = data.aws_iam_policy_document.upload_worker_assume[0].json

  tags = {
    Project     = var.project
    Environment = var.environment
  }
}

resource "aws_iam_role_policy_attachment" "upload_worker_basic" {
  count = local.upload_worker_enabled ? 1 : 0

  role       = aws_iam_role.upload_worker[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "upload_worker_vpc" {
  count = local.upload_worker_enabled ? 1 : 0

  role       = aws_iam_role.upload_worker[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

data "aws_iam_policy_document" "upload_worker_inline" {
  count = local.upload_worker_enabled ? 1 : 0

  statement {
    sid    = "S3UploadsRW"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:HeadObject",
      "s3:DeleteObject",
    ]
    resources = ["${aws_s3_bucket.uploads.arn}/*"]
  }

  statement {
    sid       = "SqsConsume"
    effect    = "Allow"
    actions   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes", "sqs:ChangeMessageVisibility"]
    resources = [aws_sqs_queue.upload_jobs[0].arn]
  }

  statement {
    sid    = "ReadRuntimeSecrets"
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue",
    ]
    resources = compact([
      aws_secretsmanager_secret.apprunner_database_url[0].arn,
      trimspace(local.apprunner_openrouter_secret_arn) != "" ? local.apprunner_openrouter_secret_arn : null,
      trimspace(local.telegram_secret_arn) != "" ? local.telegram_secret_arn : null,
    ])
  }
}

resource "aws_iam_role_policy" "upload_worker_inline" {
  count = local.upload_worker_enabled ? 1 : 0

  name   = "upload-worker-inline"
  role   = aws_iam_role.upload_worker[0].id
  policy = data.aws_iam_policy_document.upload_worker_inline[0].json
}

resource "aws_lambda_function" "upload_worker" {
  count = local.upload_worker_lambda_enabled ? 1 : 0

  function_name = substr("${var.project}-${var.environment}-upload-worker", 0, 64)
  role          = aws_iam_role.upload_worker[0].arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.upload_worker[0].repository_url}:${var.upload_worker_image_tag}"
  architectures = ["x86_64"]

  timeout     = 900
  memory_size = 2048

  vpc_config {
    subnet_ids         = local.rds_subnet_ids
    security_group_ids = [aws_security_group.api_rds_client[0].id]
  }

  environment {
    variables = merge(
      {
        AWS_S3_BUCKET                = aws_s3_bucket.uploads.bucket
        LAMBDA_DATABASE_SECRET_ARN   = aws_secretsmanager_secret.apprunner_database_url[0].arn
        LAMBDA_OPENROUTER_SECRET_ARN = local.apprunner_openrouter_secret_arn
        OPENROUTER_BASE_URL          = var.apprunner_openrouter_base_url
        OPENROUTER_MODEL             = var.apprunner_openrouter_model
        PUBLIC_BASE_URL = (
          var.apprunner_public_base_url != ""
          ? var.apprunner_public_base_url
          : "https://${aws_apprunner_service.api[0].service_url}"
        )
        UPLOAD_JOBS_QUEUE_URL = aws_sqs_queue.upload_jobs[0].url
      },
      trimspace(local.telegram_secret_arn) != "" ? {
        LAMBDA_TELEGRAM_BOT_SECRET_ARN = local.telegram_secret_arn
      } : {},
      length(trimspace(var.telegram_chat_ids)) > 0 ? {
        TELEGRAM_CHAT_IDS = trimspace(var.telegram_chat_ids)
      } : {},
      (
        trimspace(local.telegram_secret_arn) != "" || length(trimspace(var.telegram_chat_ids)) > 0
        ) ? {
        TELEGRAM_HIL_CONFIDENCE_BELOW = tostring(var.telegram_hil_confidence_below)
      } : {},
      length(local.hil_frontend_base) > 0 ? { FRONTEND_PUBLIC_BASE_URL = local.hil_frontend_base } : {},
    )
  }

  tags = {
    Project     = var.project
    Environment = var.environment
  }

  depends_on = [
    aws_iam_role_policy_attachment.upload_worker_basic,
    aws_iam_role_policy_attachment.upload_worker_vpc,
    aws_iam_role_policy.upload_worker_inline,
  ]
}

resource "aws_lambda_event_source_mapping" "upload_jobs" {
  count = local.upload_worker_lambda_enabled ? 1 : 0

  event_source_arn = aws_sqs_queue.upload_jobs[0].arn
  function_name    = aws_lambda_function.upload_worker[0].arn
  batch_size       = 1
  enabled          = true
}

data "aws_iam_policy_document" "apprunner_instance_sqs_send" {
  count = local.upload_worker_enabled ? 1 : 0

  statement {
    sid       = "SqsSendUploadJobs"
    effect    = "Allow"
    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.upload_jobs[0].arn]
  }
}

resource "aws_iam_role_policy" "apprunner_instance_sqs_send" {
  count = local.upload_worker_enabled ? 1 : 0

  name   = "sqs-send-upload-jobs"
  role   = aws_iam_role.apprunner_instance[0].id
  policy = data.aws_iam_policy_document.apprunner_instance_sqs_send[0].json
}
