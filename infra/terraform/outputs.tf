output "aws_account_id" {
  description = "Current AWS account ID (optional in .env for docs/ARNs; not a login credential)."
  value       = data.aws_caller_identity.current.account_id
}

output "uploads_bucket_name" {
  description = "Set AWS_S3_BUCKET in the API to this value."
  value       = aws_s3_bucket.uploads.bucket
}

output "uploads_bucket_arn" {
  value = aws_s3_bucket.uploads.arn
}

output "ecr_repository_url" {
  description = "ECR repository URL without tag; use as docker push destination with :TAG appended."
  value       = aws_ecr_repository.api.repository_url
}

output "ecr_repository_arn" {
  value = aws_ecr_repository.api.arn
}

output "upload_jobs_queue_url" {
  description = "SQS queue URL for async uploads (same value as UPLOAD_JOBS_QUEUE_URL on App Runner when upload_async_pipeline_enabled)."
  value       = try(aws_sqs_queue.upload_jobs[0].url, null)
}

output "upload_worker_ecr_url" {
  description = "ECR repository URL for the upload-worker Lambda image (no tag)."
  value       = try(aws_ecr_repository.upload_worker[0].repository_url, null)
}

output "upload_worker_lambda_arn" {
  description = "Lambda function ARN when upload_worker_create_lambda is true and the pipeline is enabled; null if Lambda is deferred or off."
  value       = try(aws_lambda_function.upload_worker[0].arn, null)
}

output "github_actions_role_arn" {
  description = "GitHub Actions: set secret AWS_DEPLOY_ROLE_ARN to this (OIDC push to ECR)."
  value       = try(aws_iam_role.github_ecr_push[0].arn, null)
}

output "api_task_uploads_policy_arn" {
  description = "Attach to the API service instance/task role so the app can read/write proof objects in S3."
  value       = aws_iam_policy.api_task_uploads.arn
}

output "rds_address" {
  description = "RDS hostname (when rds_enabled)."
  value       = try(aws_db_instance.main[0].address, null)
}

output "rds_port" {
  description = "Postgres port (when rds_enabled)."
  value       = try(aws_db_instance.main[0].port, null)
}

output "rds_database_name" {
  description = "Initial database name (when rds_enabled)."
  value       = try(aws_db_instance.main[0].db_name, null)
}

output "rds_master_username" {
  description = "Master username (when rds_enabled)."
  value       = try(aws_db_instance.main[0].username, null)
}

output "rds_master_password" {
  description = "Master password (sensitive). Prefer rotating after first deploy."
  value       = try(random_password.rds_master[0].result, null)
  sensitive   = true
}

output "rds_security_group_id" {
  description = "Security group attached to the RDS instance (server side)."
  value       = try(aws_security_group.rds[0].id, null)
}

output "api_rds_client_security_group_id" {
  description = "Attach this security group to your API service (task / VPC connector / ENI). RDS allows 5432 from it. Null if rds_create_api_client_security_group is false."
  value       = try(aws_security_group.api_rds_client[0].id, null)
}

output "database_url" {
  description = "Ready-to-paste DATABASE_URL for this app (postgresql+asyncpg). terraform output -raw database_url"
  value = var.rds_enabled ? format(
    "postgresql+asyncpg://%s:%s@%s:%s/%s?%s",
    aws_db_instance.main[0].username,
    urlencode(random_password.rds_master[0].result),
    aws_db_instance.main[0].address,
    tostring(aws_db_instance.main[0].port),
    coalesce(aws_db_instance.main[0].db_name, var.rds_database_name),
    var.rds_connection_query,
  ) : null
  sensitive = true
}

output "apprunner_service_arn" {
  description = "App Runner service ARN (when apprunner_enabled)."
  value       = try(aws_apprunner_service.api[0].arn, null)
}

output "apprunner_service_url" {
  description = "App Runner default hostname only (no scheme), e.g. xxx.eu-west-1.awsapprunner.com (when apprunner_enabled)."
  value       = try(aws_apprunner_service.api[0].service_url, null)
}

output "apprunner_public_url" {
  description = "Suggested PUBLIC_BASE_URL / HTTPS origin: https://<apprunner_service_url> (when apprunner_enabled)."
  value       = try("https://${aws_apprunner_service.api[0].service_url}", null)
}

output "apprunner_database_secret_arn" {
  description = "Secrets Manager ARN for DATABASE_URL when Terraform manages it (rds_enabled + apprunner_enabled); null otherwise."
  value       = try(aws_secretsmanager_secret.apprunner_database_url[0].arn, null)
}

output "apprunner_openrouter_secret_arn" {
  description = "Secrets Manager ARN for OPENROUTER_API_KEY when apprunner_create_openrouter_secret is true; null otherwise."
  value       = try(aws_secretsmanager_secret.openrouter_api_key[0].arn, null)
}

output "frontend_cloudfront_domain_name" {
  description = "CloudFront domain (xxx.cloudfront.net) when frontend_cloudfront_enabled."
  value       = try(aws_cloudfront_distribution.frontend[0].domain_name, null)
}

output "frontend_cloudfront_distribution_id" {
  description = "CloudFront distribution id for cache invalidation (e.g. GitHub Actions) when frontend_cloudfront_enabled."
  value       = try(aws_cloudfront_distribution.frontend[0].id, null)
}

output "frontend_cloudfront_url" {
  description = "HTTPS URL of the static dashboard when frontend_cloudfront_enabled."
  value       = try("https://${aws_cloudfront_distribution.frontend[0].domain_name}", null)
}

output "frontend_s3_bucket_id" {
  description = "S3 bucket id for static export objects (when frontend_cloudfront_enabled)."
  value       = try(aws_s3_bucket.frontend[0].id, null)
}

output "apprunner_nat_gateway_id" {
  description = "NAT gateway id when apprunner_manage_nat_gateway is true with App Runner + RDS; null otherwise."
  value       = try(aws_nat_gateway.apprunner_nat[0].id, null)
}

output "apprunner_nat_dedicated_public_subnet_id" {
  description = "When apprunner_nat_create_dedicated_public_subnet is true: the small public subnet Terraform created for NAT only; null otherwise."
  value       = length(aws_subnet.apprunner_nat_public_dedicated) > 0 ? aws_subnet.apprunner_nat_public_dedicated[0].id : null
}

output "apprunner_nat_elastic_ip" {
  description = "Public IPv4 of the NAT EIP when apprunner_manage_nat_gateway is true; null otherwise."
  value       = try(aws_eip.apprunner_nat[0].public_ip, null)
}

output "apprunner_nat_replace_default_route_commands" {
  description = "AWS CLI lines: replace 0.0.0.0/0 with NAT on each App Runner connector route table (same as RDS subnet route tables). Idempotent — safe to re-run if OpenRouter HTTPS from App Runner times out. Always a string when NAT is enabled so `terraform output` works (Terraform omits null outputs from state)."
  value = (
    !local.apprunner_nat_enabled
    ? "(apprunner_manage_nat_gateway is off or App Runner/RDS not enabled — no NAT replace-route commands.)"
    : length(local.apprunner_connector_route_table_ids) == 0
    ? "(No connector route tables in state — check rds_subnet_ids / NAT.)"
    : join("\n", [
      for rtb_id in sort(local.apprunner_connector_route_table_ids) :
      "aws ec2 replace-route --region ${var.aws_region} --route-table-id ${rtb_id} --destination-cidr-block 0.0.0.0/0 --nat-gateway-id ${aws_nat_gateway.apprunner_nat[0].id}"
    ])
  )
}

output "apprunner_vpc_connector_subnet_ids" {
  description = "Subnets used by the App Runner VPC connector (same as RDS subnets in this stack). Each subnet's default route must send 0.0.0.0/0 to the NAT gateway for OpenRouter HTTPS."
  value       = local.rds_subnet_ids
}

output "apprunner_vpc_connector_route_table_ids" {
  description = "Route tables associated with those subnets when NAT management is enabled (empty list otherwise)."
  value       = local.apprunner_connector_route_table_ids
}

output "apprunner_nat_route_tables_using_igw_for_internet" {
  description = "Route tables where Terraform saw 0.0.0.0/0 -> Internet Gateway; App Runner ENIs cannot use that path. Run apprunner_nat_replace_default_route_commands (same lines) after apply."
  value       = local.apprunner_nat_enabled ? sort(tolist(local.apprunner_nat_route_table_ids_ipv4_default_igw)) : []
}
