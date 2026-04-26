variable "aws_region" {
  type        = string
  description = "Region for the state bucket and lock table."
  default     = "eu-west-1"
}

variable "project" {
  type        = string
  description = "Short prefix (must match main stack project)."
}

variable "environment" {
  type        = string
  description = "Environment segment (must match main stack environment)."
}
