variable "aws_region" {
  type        = string
  description = "AWS region for all resources."
  default     = "eu-west-1"
}

variable "project" {
  type        = string
  description = "Short name prefix for resources (e.g. audit-nigeria)."
  default     = "audit-nigeria"
}

variable "environment" {
  type        = string
  description = "Environment segment (e.g. prod, staging)."
  default     = "prod"
}

variable "github_org" {
  type        = string
  description = "GitHub org or user (for OIDC trust). Leave empty to skip GitHub IAM role."
  default     = ""
}

variable "github_repo" {
  type        = string
  description = "GitHub repository name under github_org."
  default     = ""
}

variable "github_branch_ref" {
  type        = string
  description = "Restrict OIDC role to this ref (e.g. ref:refs/heads/main)."
  default     = "ref:refs/heads/main"
}

# --- Optional RDS PostgreSQL (default VPC) ---

variable "rds_enabled" {
  type        = bool
  description = "Create an RDS PostgreSQL instance (adds AWS monthly cost). Requires default VPC with ≥2 subnets or rds_subnet_ids. When App Runner is enabled too, the service uses VPC egress to reach RDS: the VPC connector subnets need outbound internet (usually a NAT gateway in a public subnet) for HTTPS to OpenRouter and other public APIs; otherwise uploads will fail with httpx ConnectTimeout."
  default     = false
}

variable "rds_create_api_client_security_group" {
  type        = bool
  description = "Create a security group to attach to your API (ECS/App Runner/EC2). RDS allows Postgres from this SG plus any IDs in rds_allowed_security_group_ids."
  default     = true
}

variable "rds_subnet_ids" {
  type        = list(string)
  description = "Exactly two subnet IDs in different AZs (RDS + App Runner VPC connector). Leave empty to auto-pick one subnet from each of the first two regional availability zones in the default VPC (not lexically first two subnet IDs). Never pass a single subnet — RDS requires ≥2 AZs."
  default     = []

  validation {
    condition     = length(var.rds_subnet_ids) == 0 || length(var.rds_subnet_ids) >= 2
    error_message = "rds_subnet_ids must be empty (use auto-pick) or contain at least two subnet IDs in different availability zones."
  }
}

variable "rds_allowed_cidr_blocks" {
  type        = list(string)
  description = "CIDRs allowed to reach Postgres on 5432 (e.g. [\"203.0.113.10/32\"]). Use with rds_publicly_accessible=true for dev."
  default     = []
}

variable "rds_allowed_security_group_ids" {
  type        = list(string)
  description = "Extra security group IDs allowed to reach Postgres on 5432 (merged with the managed API client SG when rds_create_api_client_security_group is true)."
  default     = []
}

variable "rds_engine_version" {
  type    = string
  default = "15"
}

variable "rds_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "rds_allocated_storage" {
  type    = number
  default = 20
}

variable "rds_max_allocated_storage" {
  type        = number
  description = "Storage autoscaling cap (GiB). 0 disables autoscaling."
  default     = 0
}

variable "rds_database_name" {
  type    = string
  default = "audit_nigeria"
}

variable "rds_master_username" {
  type    = string
  default = "auditadmin"
}

variable "rds_publicly_accessible" {
  type        = bool
  description = "If true, RDS gets a public IP (typical for dev + default VPC). Use false when the API connects from the same private VPC only."
  default     = true
}

variable "rds_skip_final_snapshot" {
  type        = bool
  description = "If true, destroying the instance does not create a final DB snapshot (dev only)."
  default     = true
}

variable "rds_backup_retention_days" {
  type    = number
  default = 1
}

variable "rds_deletion_protection" {
  type    = bool
  default = false
}

variable "rds_connection_query" {
  type        = string
  description = "Query string appended to DATABASE_URL (e.g. ssl=require for RDS TLS)."
  default     = "ssl=require"
}

# --- Optional App Runner (ECR image; VPC egress to RDS when rds_enabled) ---

variable "apprunner_enabled" {
  type        = bool
  description = "Create an App Runner service for the API (pulls from this stack's ECR). Requires an image tag already pushed (e.g. manual-1)."
  default     = false
}

variable "apprunner_image_tag" {
  type        = string
  description = "ECR image tag for the API (must exist before apply)."
  default     = "latest"
}

variable "apprunner_cpu" {
  type        = string
  description = "App Runner CPU units (1024 = 0.25 vCPU). POST /upload runs CPU-heavy blur before OpenRouter; 0.25 vCPU can approach App Runner's ~120s HTTP limit on large images — use 2048+ (0.5 vCPU) if uploads hit 502 with x-envoy-upstream-service-time ~118000."
  default     = "1024"
}

variable "apprunner_memory" {
  type        = string
  description = "App Runner memory in MiB (must be valid for chosen CPU)."
  default     = "2048"
}

variable "apprunner_auto_deployments_enabled" {
  type        = bool
  description = "If true, App Runner deploys on every ECR image push; if false, change apprunner_image_tag (or console) to roll out."
  default     = false
}

variable "apprunner_vpc_connector_destroy_sleep_seconds" {
  type        = number
  description = "Before DeleteVpcConnector runs (create_before_destroy replacement), wait this many seconds via Python (must be on PATH). App Runner often keeps a reference to the old connector for several minutes after the service switches. Default 660. Set 0 to skip (then re-run apply if delete fails)."
  default     = 660
}

variable "apprunner_public_base_url" {
  type        = string
  description = "HTTPS URL of the API with no trailing slash (e.g. https://xxxx.eu-west-1.awsapprunner.com). Leave empty on first apply; run apply again after copying output apprunner_public_url."
  default     = ""
}

variable "apprunner_cors_allow_origins" {
  type        = string
  description = "Comma-separated *extra* CORS origins for App Runner (e.g. http://localhost:3000). When frontend_cloudfront_enabled, Terraform appends the CloudFront HTTPS origin; you do not need to duplicate it here."
  default     = ""
}

variable "apprunner_expose_errors" {
  type        = bool
  description = "Maps to APP_EXPOSE_ERRORS on the container (use false in production)."
  default     = false
}

variable "apprunner_openrouter_base_url" {
  type        = string
  description = "OPENROUTER_BASE_URL for the container."
  default     = "https://openrouter.ai/api/v1"
}

variable "apprunner_openrouter_model" {
  type        = string
  description = "OPENROUTER_MODEL for the container."
  default     = "anthropic/claude-sonnet-4.5"
}

variable "apprunner_openrouter_api_key_secret_arn" {
  type        = string
  description = "Optional existing Secrets Manager secret ARN (plain string = OpenRouter key → OPENROUTER_API_KEY). Leave empty if using apprunner_create_openrouter_secret instead."
  default     = ""
}

variable "apprunner_create_openrouter_secret" {
  type        = bool
  description = "When true with apprunner_enabled, Terraform creates aws_secretsmanager_secret + version from apprunner_openrouter_api_key and wires App Runner OPENROUTER_API_KEY to it. Do not set apprunner_openrouter_api_key_secret_arn at the same time."
  default     = false
}

variable "apprunner_openrouter_api_key" {
  type        = string
  description = "OpenRouter API key (plain string). Used only when apprunner_create_openrouter_secret is true. Sensitive — use terraform.tfvars (gitignored) or TF_VAR_apprunner_openrouter_api_key, never commit."
  default     = ""
  sensitive   = true
}

variable "apprunner_manage_nat_gateway" {
  type        = bool
  description = "When true with apprunner_enabled and rds_enabled, create one NAT gateway + EIP and manage 0.0.0.0/0 -> NAT on connector subnets where safe. NAT must sit in a true public subnet (IGW default route): use apprunner_nat_create_dedicated_public_subnet + CIDR, or set apprunner_nat_public_subnet_id. Set false if your VPC already has NAT or you manage routes elsewhere."
  default     = true
}

variable "apprunner_nat_create_dedicated_public_subnet" {
  type        = bool
  description = "When true with NAT enabled, Terraform creates a small public subnet + route table (0.0.0.0/0 -> IGW) only for the NAT gateway. Recommended for default VPC layouts where rds_subnet_ids share a NAT-only default route. Requires apprunner_nat_dedicated_subnet_ipv4_cidr to be an unused block in the VPC (e.g. /28)."
  default     = false
}

variable "apprunner_nat_dedicated_subnet_ipv4_cidr" {
  type        = string
  description = "IPv4 CIDR for the dedicated NAT public subnet (e.g. 172.31.255.240/28). Must not overlap any existing subnet in the VPC. Used only when apprunner_nat_create_dedicated_public_subnet is true."
  default     = ""
}

variable "apprunner_nat_public_subnet_id" {
  type        = string
  description = "When apprunner_nat_create_dedicated_public_subnet is false: subnet ID where the NAT gateway is created. Must be a true public subnet (route table 0.0.0.0/0 -> Internet Gateway), ideally not one of rds_subnet_ids if those use a NAT-only shared route table."
  default     = ""
}

variable "apprunner_manage_nat_ipv4_routes" {
  type        = bool
  description = "When true (default), add aws_route 0.0.0.0/0 -> NAT on connector route tables that have no IPv4 default route yet. If tables already use 0.0.0.0/0 -> IGW (default VPC), set apprunner_nat_cli_replace_igw_default_route (default true) so Terraform runs aws ec2 replace-route during apply, or use output apprunner_nat_replace_default_route_commands manually."
  default     = true
}

variable "apprunner_nat_cli_replace_igw_default_route" {
  type        = bool
  description = "When true with NAT + apprunner_manage_nat_ipv4_routes, run `aws ec2 replace-route` (requires AWS CLI on the host running terraform) to point 0.0.0.0/0 from Internet Gateway to NAT on connector subnets' route tables. Required for OpenRouter/HTTPS from App Runner in many default VPC setups. Set false to skip (e.g. locked-down CI) and run output apprunner_nat_replace_default_route_commands yourself."
  default     = true
}

variable "apprunner_database_secret_arn" {
  type        = string
  description = "When apprunner_enabled without rds_enabled: Secrets Manager ARN whose secret string is the full DATABASE_URL. Ignored when rds_enabled (Terraform creates the secret)."
  default     = ""
}

variable "apprunner_secret_recovery_window_days" {
  type        = number
  description = "Recovery window for the Terraform-managed DATABASE_URL secret (when rds_enabled)."
  default     = 0
}

variable "apprunner_run_db_seed" {
  type        = bool
  description = "If true, sets RUN_DB_SEED=1 on the container so `python -m app.db.seed` runs once at startup (before uvicorn). Idempotent; set false after first successful rollout."
  default     = false
}

variable "apprunner_dashboard_reset_token" {
  type        = string
  description = "Optional. When non-empty, sets DASHBOARD_RESET_TOKEN on App Runner so POST /demo/reset-collated-votes + upload UI reset CTA work. Use a long random string; sensitive."
  default     = ""
  sensitive   = true
}

variable "upload_async_pipeline_enabled" {
  type        = bool
  description = "When true with apprunner_enabled, rds_enabled, and rds_create_api_client_security_group: create SQS + ECR + IAM for upload-worker, S3 CORS for presigned PUT, wire UPLOAD_JOBS_QUEUE_URL on App Runner. The Lambda itself is created only when upload_worker_create_lambda is true and the image already exists in ECR (see upload_worker_image_tag)."
  default     = false
}

variable "upload_worker_create_lambda" {
  type        = bool
  description = "When true with upload_async_pipeline_enabled: create the container Lambda and SQS trigger. Requires an image at upload_worker_ecr_url:upload_worker_image_tag. Set false on the first apply after enabling the pipeline, run infra/scripts/push-upload-worker.ps1 (or docker push), then set true and apply again."
  default     = true
}

variable "upload_worker_image_tag" {
  type        = string
  description = "ECR image tag for the upload-worker Lambda container (must exist in ECR before Lambda can be created)."
  default     = "latest"
}

# --- Optional frontend (Next static export → S3 + CloudFront) ---

variable "frontend_cloudfront_enabled" {
  type        = bool
  description = "Create S3 + CloudFront for the dashboard. Requires `frontend/out` from STATIC_EXPORT=1 build (see infra/README.md)."
  default     = false
}

variable "frontend_static_out_dir" {
  type        = string
  description = "Path to Next static export output, relative to this Terraform module."
  default     = "../../frontend/out"
}
