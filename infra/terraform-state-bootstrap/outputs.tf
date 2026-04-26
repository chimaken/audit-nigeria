output "terraform_state_bucket" {
  description = "Set GitHub secret TF_STATE_BUCKET to this value."
  value       = aws_s3_bucket.terraform_state.bucket
}

output "terraform_state_lock_table" {
  description = "Set GitHub secret TF_STATE_LOCK_TABLE to this value."
  value       = aws_dynamodb_table.terraform_lock.name
}

output "aws_region" {
  value = var.aws_region
}

output "suggested_tf_state_key" {
  description = "Suggested TF_STATE_KEY repo variable (state object key inside the bucket)."
  value       = "${var.project}/${var.environment}/terraform.tfstate"
}
