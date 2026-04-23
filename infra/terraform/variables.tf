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
