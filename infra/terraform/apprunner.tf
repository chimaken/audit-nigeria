# Optional AWS App Runner service: pulls API image from ECR, VPC egress to RDS when rds_enabled.

locals {
  apprunner_db_secret_arn = var.apprunner_enabled && var.rds_enabled ? aws_secretsmanager_secret.apprunner_database_url[0].arn : (
    var.apprunner_enabled ? var.apprunner_database_secret_arn : ""
  )

  # OPENROUTER_API_KEY: either Terraform-managed secret or caller-supplied ARN (not both — see check block).
  apprunner_openrouter_secret_arn = (
    length(aws_secretsmanager_secret.openrouter_api_key) > 0
    ? aws_secretsmanager_secret.openrouter_api_key[0].arn
    : trimspace(var.apprunner_openrouter_api_key_secret_arn)
  )

  telegram_secret_arn = (
    length(aws_secretsmanager_secret.telegram_bot) > 0
    ? aws_secretsmanager_secret.telegram_bot[0].arn
    : trimspace(var.telegram_bot_token_secret_arn)
  )

  hil_frontend_base = (
    trimspace(var.hil_frontend_public_base_url) != ""
    ? trimsuffix(trimspace(var.hil_frontend_public_base_url), "/")
    : (
      var.frontend_cloudfront_enabled
      ? "https://${aws_cloudfront_distribution.frontend[0].domain_name}"
      : ""
    )
  )

  apprunner_secret_arn_by_name = merge(
    local.apprunner_db_secret_arn != "" ? { "DATABASE_URL" = local.apprunner_db_secret_arn } : {},
    local.apprunner_openrouter_secret_arn != "" ? {
      "OPENROUTER_API_KEY" = local.apprunner_openrouter_secret_arn
    } : {},
    local.telegram_secret_arn != "" ? { TELEGRAM_BOT_TOKEN = local.telegram_secret_arn } : {},
  )

  cloudfront_dashboard_origin = var.frontend_cloudfront_enabled ? "https://${aws_cloudfront_distribution.frontend[0].domain_name}" : ""

  apprunner_cors_merged = join(",", distinct(compact(concat(
    [
      for x in split(",", var.apprunner_cors_allow_origins) :
      trimsuffix(trimspace(x), "/") if trimspace(x) != ""
    ],
    local.cloudfront_dashboard_origin != "" ? [trimsuffix(local.cloudfront_dashboard_origin, "/")] : [],
  ))))

  # Include a hash of subnet IDs so the name changes when subnets change; required for
  # create_before_destroy (otherwise AWS rejects deleting a connector still in use).
  apprunner_vpc_connector_name = substr(
    "${var.project}-${var.environment}-vc-${substr(sha256(join(",", sort(local.rds_subnet_ids))), 0, 8)}",
    0,
    40,
  )

  apprunner_runtime_env = merge(
    {
      AWS_S3_BUCKET       = aws_s3_bucket.uploads.bucket
      AWS_REGION          = var.aws_region
      APP_EXPOSE_ERRORS   = tostring(var.apprunner_expose_errors)
      OPENROUTER_BASE_URL = var.apprunner_openrouter_base_url
      OPENROUTER_MODEL    = var.apprunner_openrouter_model
    },
    var.apprunner_public_base_url != "" ? { PUBLIC_BASE_URL = var.apprunner_public_base_url } : {},
    length(local.apprunner_cors_merged) > 0 ? { CORS_ALLOW_ORIGINS = local.apprunner_cors_merged } : {},
    var.apprunner_run_db_seed ? { RUN_DB_SEED = "1" } : {},
    length(trimspace(var.apprunner_dashboard_reset_token)) > 0 ? {
      DASHBOARD_RESET_TOKEN = var.apprunner_dashboard_reset_token
    } : {},
    length(aws_sqs_queue.upload_jobs) > 0 ? { UPLOAD_JOBS_QUEUE_URL = aws_sqs_queue.upload_jobs[0].url } : {},
    length(local.hil_frontend_base) > 0 ? { FRONTEND_PUBLIC_BASE_URL = local.hil_frontend_base } : {},
    length(trimspace(var.telegram_chat_ids)) > 0 ? { TELEGRAM_CHAT_IDS = trimspace(var.telegram_chat_ids) } : {},
    (
      local.telegram_secret_arn != "" || length(trimspace(var.telegram_chat_ids)) > 0
      ) ? {
      TELEGRAM_HIL_CONFIDENCE_BELOW = tostring(var.telegram_hil_confidence_below)
    } : {},
  )
}

check "apprunner_rds_client_sg" {
  assert {
    condition     = !var.apprunner_enabled || !var.rds_enabled || var.rds_create_api_client_security_group
    error_message = "When apprunner_enabled and rds_enabled, set rds_create_api_client_security_group = true so the VPC connector can use the managed API client security group."
  }
}

check "apprunner_database_secret_when_no_rds" {
  assert {
    condition     = !var.apprunner_enabled || var.rds_enabled || length(var.apprunner_database_secret_arn) > 0
    error_message = "When apprunner_enabled without rds_enabled, set apprunner_database_secret_arn to a Secrets Manager secret ARN whose string value is the full DATABASE_URL (postgresql+asyncpg://...)."
  }
}

check "openrouter_secret_single_source" {
  assert {
    condition = !(
      var.apprunner_create_openrouter_secret &&
      trimspace(var.apprunner_openrouter_api_key_secret_arn) != ""
    )
    error_message = "Use only one of apprunner_create_openrouter_secret (+ apprunner_openrouter_api_key) or apprunner_openrouter_api_key_secret_arn, not both."
  }
}

resource "aws_secretsmanager_secret" "openrouter_api_key" {
  count = var.apprunner_enabled && var.apprunner_create_openrouter_secret ? 1 : 0

  name                    = "${var.project}/${var.environment}/openrouter-api-key"
  recovery_window_in_days = var.apprunner_secret_recovery_window_days

  tags = {
    Project     = var.project
    Environment = var.environment
    Purpose     = "openrouter-api-key"
  }
}

resource "aws_secretsmanager_secret_version" "openrouter_api_key" {
  count = var.apprunner_enabled && var.apprunner_create_openrouter_secret ? 1 : 0

  secret_id     = aws_secretsmanager_secret.openrouter_api_key[0].id
  secret_string = var.apprunner_openrouter_api_key
}

resource "aws_secretsmanager_secret" "apprunner_database_url" {
  count = var.apprunner_enabled && var.rds_enabled ? 1 : 0

  name                    = "${var.project}/${var.environment}/apprunner-database-url"
  recovery_window_in_days = var.apprunner_secret_recovery_window_days

  tags = {
    Project     = var.project
    Environment = var.environment
  }
}

resource "aws_secretsmanager_secret_version" "apprunner_database_url" {
  count = var.apprunner_enabled && var.rds_enabled ? 1 : 0

  secret_id = aws_secretsmanager_secret.apprunner_database_url[0].id
  secret_string = format(
    "postgresql+asyncpg://%s:%s@%s:%s/%s?%s",
    aws_db_instance.main[0].username,
    urlencode(random_password.rds_master[0].result),
    aws_db_instance.main[0].address,
    tostring(aws_db_instance.main[0].port),
    coalesce(aws_db_instance.main[0].db_name, var.rds_database_name),
    var.rds_connection_query,
  )
}

# App Runner rejects creating a second VPC connector that reuses the same security group list while
# the old connector still exists. A companion SG (rotating when subnets change) makes each connector unique.
resource "random_id" "apprunner_vpc_connector_distinct" {
  count = var.apprunner_enabled && var.rds_enabled ? 1 : 0

  keepers = {
    subnets = join(",", sort(local.rds_subnet_ids))
  }
  byte_length = 4
}

resource "aws_security_group" "apprunner_vpc_connector_distinct" {
  count = var.apprunner_enabled && var.rds_enabled ? 1 : 0

  name_prefix = substr("${var.project}-${var.environment}-aprvpc-${random_id.apprunner_vpc_connector_distinct[0].hex}-", 0, 220)
  description = "Companion SG for App Runner VPC connector (AWS requires a unique SG set per connector during create-before-destroy). ENI also uses api_rds_client for RDS."
  vpc_id      = data.aws_vpc.default[0].id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Project     = var.project
    Environment = var.environment
    Purpose     = "apprunner-vpc-connector-distinct"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_apprunner_vpc_connector" "api" {
  count = var.apprunner_enabled && var.rds_enabled ? 1 : 0

  vpc_connector_name = local.apprunner_vpc_connector_name
  subnets            = local.rds_subnet_ids
  security_groups = [
    aws_security_group.api_rds_client[0].id,
    aws_security_group.apprunner_vpc_connector_distinct[0].id,
  ]

  tags = {
    Project     = var.project
    Environment = var.environment
    # Destroy provisioner may only reference `self` (not var/locals); drives pre-delete wait for AWS propagation.
    terraform_destroy_sleep_sec = tostring(var.apprunner_vpc_connector_destroy_sleep_seconds)
  }

  lifecycle {
    create_before_destroy = true
  }

  # AWS may still consider the old connector "in use" for minutes after UpdateService points at the new ARN.
  provisioner "local-exec" {
    when    = destroy
    command = <<-EOT
python -c "import time; time.sleep(max(0, int('${lookup(self.tags, "terraform_destroy_sleep_sec", "660")}')))"
EOT
  }
}

# App Runner assumes this role to pull images from private ECR.
resource "aws_iam_role" "apprunner_ecr_access" {
  count = var.apprunner_enabled ? 1 : 0

  name = substr("${var.project}-${var.environment}-apprunner-ecr", 0, 64)

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "build.apprunner.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = {
    Project     = var.project
    Environment = var.environment
  }
}

resource "aws_iam_role_policy_attachment" "apprunner_ecr_access" {
  count = var.apprunner_enabled ? 1 : 0

  role       = aws_iam_role.apprunner_ecr_access[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
}

# Task role: S3 uploads policy + read DATABASE_URL / OpenRouter secrets.
resource "aws_iam_role" "apprunner_instance" {
  count = var.apprunner_enabled ? 1 : 0

  name = substr("${var.project}-${var.environment}-apprunner-instance", 0, 64)

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "tasks.apprunner.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = {
    Project     = var.project
    Environment = var.environment
  }
}

resource "aws_iam_role_policy_attachment" "apprunner_instance_s3" {
  count = var.apprunner_enabled ? 1 : 0

  role       = aws_iam_role.apprunner_instance[0].name
  policy_arn = aws_iam_policy.api_task_uploads.arn
}

# Count must not depend on secret ARNs (unknown until apply). Policy body may still reference those ARNs.
data "aws_iam_policy_document" "apprunner_instance_secrets" {
  count = var.apprunner_enabled ? 1 : 0

  statement {
    sid     = "ReadRuntimeSecrets"
    effect  = "Allow"
    actions = ["secretsmanager:GetSecretValue"]
    resources = compact(distinct([
      local.apprunner_db_secret_arn,
      local.apprunner_openrouter_secret_arn,
      local.telegram_secret_arn,
    ]))
  }
}

resource "aws_iam_role_policy" "apprunner_instance_secrets" {
  count = var.apprunner_enabled ? 1 : 0

  name   = "runtime-secrets"
  role   = aws_iam_role.apprunner_instance[0].id
  policy = data.aws_iam_policy_document.apprunner_instance_secrets[0].json
}

resource "aws_apprunner_service" "api" {
  count = var.apprunner_enabled ? 1 : 0

  service_name = substr("${var.project}-${var.environment}-api", 0, 40)

  source_configuration {
    auto_deployments_enabled = var.apprunner_auto_deployments_enabled

    authentication_configuration {
      access_role_arn = aws_iam_role.apprunner_ecr_access[0].arn
    }

    image_repository {
      image_identifier      = "${aws_ecr_repository.api.repository_url}:${var.apprunner_image_tag}"
      image_repository_type = "ECR"

      image_configuration {
        port                          = "8000"
        runtime_environment_variables = local.apprunner_runtime_env
        # Map: env name -> Secrets Manager secret ARN (plain string secret value).
        runtime_environment_secrets = local.apprunner_secret_arn_by_name
      }
    }
  }

  instance_configuration {
    cpu               = var.apprunner_cpu
    memory            = var.apprunner_memory
    instance_role_arn = aws_iam_role.apprunner_instance[0].arn
  }

  dynamic "network_configuration" {
    for_each = var.apprunner_enabled && var.rds_enabled ? [1] : []
    content {
      ingress_configuration {
        is_publicly_accessible = true
      }
      # Outbound uses connector subnets' route tables (see nat_gateway.tf: NAT + 0.0.0.0/0 -> NAT when enabled).
      egress_configuration {
        egress_type       = "VPC"
        vpc_connector_arn = aws_apprunner_vpc_connector.api[0].arn
      }
    }
  }

  health_check_configuration {
    protocol            = "HTTP"
    path                = "/health"
    interval            = 10
    timeout             = 5
    healthy_threshold   = 1
    unhealthy_threshold = 5
  }

  tags = {
    Project     = var.project
    Environment = var.environment
  }

  depends_on = [
    aws_iam_role_policy_attachment.apprunner_ecr_access[0],
    aws_iam_role_policy_attachment.apprunner_instance_s3[0],
    aws_iam_role_policy.apprunner_instance_secrets[0],
  ]
}
