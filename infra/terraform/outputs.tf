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

output "github_actions_role_arn" {
  description = "GitHub Actions: set secret AWS_DEPLOY_ROLE_ARN to this (OIDC push to ECR)."
  value       = try(aws_iam_role.github_ecr_push[0].arn, null)
}

output "api_task_uploads_policy_arn" {
  description = "Attach to the API service instance/task role so the app can read/write proof objects in S3."
  value       = aws_iam_policy.api_task_uploads.arn
}
