# Human-in-the-loop: Telegram + dashboard base URL + optional one-shot SQL migration.

check "telegram_bot_secret_single_source" {
  assert {
    condition = !(
      var.telegram_create_secret &&
      trimspace(var.telegram_bot_token_secret_arn) != ""
    )
    error_message = "Use only one of telegram_create_secret (+ telegram_bot_token) or telegram_bot_token_secret_arn, not both."
  }
}

check "telegram_create_requires_token" {
  assert {
    condition     = !var.telegram_create_secret || trimspace(var.telegram_bot_token) != ""
    error_message = "When telegram_create_secret is true, set telegram_bot_token in terraform.tfvars (include it in TFVARS_B64 for GitHub Actions, or use TF_VAR_telegram_bot_token locally). Do not commit the token."
  }
}

resource "aws_secretsmanager_secret" "telegram_bot" {
  count = var.apprunner_enabled && var.telegram_create_secret ? 1 : 0

  name                    = "${var.project}/${var.environment}/telegram-bot-token"
  recovery_window_in_days = var.apprunner_secret_recovery_window_days

  tags = {
    Project     = var.project
    Environment = var.environment
    Purpose     = "telegram-bot-token"
  }
}

resource "aws_secretsmanager_secret_version" "telegram_bot" {
  count = var.apprunner_enabled && var.telegram_create_secret ? 1 : 0

  secret_id     = aws_secretsmanager_secret.telegram_bot[0].id
  secret_string = var.telegram_bot_token
}

# Runs from the machine executing terraform (needs psql + TCP route to RDS). Not for GitHub-hosted runners against private RDS.
resource "null_resource" "human_review_alert_column" {
  count = var.apprunner_enabled && var.rds_enabled && var.apply_human_review_sql_migration ? 1 : 0

  triggers = {
    sql_md5 = filemd5("${path.module}/../../backend/sql/patch_human_review_alert.sql")
  }

  provisioner "local-exec" {
    environment = {
      PGPASSWORD = random_password.rds_master[0].result
      PGHOST     = aws_db_instance.main[0].address
      PGPORT     = tostring(aws_db_instance.main[0].port)
      PGUSER     = aws_db_instance.main[0].username
      PGDATABASE = coalesce(aws_db_instance.main[0].db_name, var.rds_database_name)
    }
    command    = "psql -v ON_ERROR_STOP=1 -f \"${path.module}/../../backend/sql/patch_human_review_alert.sql\""
    on_failure = fail
  }

  depends_on = [
    aws_db_instance.main,
    aws_secretsmanager_secret_version.apprunner_database_url,
  ]
}
