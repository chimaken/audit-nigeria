# Optional Amazon RDS for PostgreSQL (default VPC). Set rds_enabled = true in terraform.tfvars.

# Cross-variable rule (not allowed on variable { validation { } } in current Terraform).
check "rds_ingress_config_when_enabled" {
  assert {
    condition = !var.rds_enabled || (
      length(var.rds_allowed_cidr_blocks) > 0
      || length(var.rds_allowed_security_group_ids) > 0
      || var.rds_create_api_client_security_group
    )
    error_message = "When rds_enabled is true, allow access via rds_allowed_cidr_blocks and/or rds_allowed_security_group_ids and/or set rds_create_api_client_security_group = true (managed API client SG)."
  }
}

data "aws_vpc" "default" {
  count   = var.rds_enabled ? 1 : 0
  default = true
}

# Auto-pick must use ≥2 *different* AZs (sorting subnet IDs often yields two subnets in the same AZ).
data "aws_availability_zones" "rds_autopick" {
  count = var.rds_enabled && length(var.rds_subnet_ids) == 0 ? 1 : 0

  state = "available"
  filter {
    name   = "opt-in-status"
    values = ["opt-in-not-required"]
  }
}

# Private / VPC-only autopick (any subnet in the first two regional AZs).
data "aws_subnets" "rds_autopick_az0_private" {
  count = var.rds_enabled && length(var.rds_subnet_ids) == 0 && !var.rds_publicly_accessible ? 1 : 0

  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default[0].id]
  }
  filter {
    name   = "availability-zone"
    values = [data.aws_availability_zones.rds_autopick[0].names[0]]
  }
}

data "aws_subnets" "rds_autopick_az1_private" {
  count = var.rds_enabled && length(var.rds_subnet_ids) == 0 && !var.rds_publicly_accessible ? 1 : 0

  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default[0].id]
  }
  filter {
    name   = "availability-zone"
    values = [data.aws_availability_zones.rds_autopick[0].names[1]]
  }
}

# Public internet path: only subnets with default-map public IP (route to IGW is typical).
# Without this, publicly_accessible=true can still sit on "private" subnets and laptop psql gets connection refused.
data "aws_subnets" "rds_autopick_az0_public" {
  count = var.rds_enabled && length(var.rds_subnet_ids) == 0 && var.rds_publicly_accessible ? 1 : 0

  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default[0].id]
  }
  filter {
    name   = "availability-zone"
    values = [data.aws_availability_zones.rds_autopick[0].names[0]]
  }
  filter {
    name   = "map-public-ip-on-launch"
    values = ["true"]
  }
}

data "aws_subnets" "rds_autopick_az1_public" {
  count = var.rds_enabled && length(var.rds_subnet_ids) == 0 && var.rds_publicly_accessible ? 1 : 0

  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default[0].id]
  }
  filter {
    name   = "availability-zone"
    values = [data.aws_availability_zones.rds_autopick[0].names[1]]
  }
  filter {
    name   = "map-public-ip-on-launch"
    values = ["true"]
  }
}

# Attach this SG to your API compute (ECS task, App Runner VPC connector, etc.); RDS allows 5432 from it + rds_allowed_security_group_ids.
resource "aws_security_group" "api_rds_client" {
  count = var.rds_enabled && var.rds_create_api_client_security_group ? 1 : 0

  name        = substr("${var.project}-${var.environment}-api-pg-client", 0, 255)
  description = "Attach to the API service so its ENI can connect to RDS (outbound rules only; RDS SG permits 5432 from this SG)."
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
    Purpose     = "rds-sql-client"
  }

  lifecycle {
    ignore_changes = [description]
  }
}

locals {
  rds_subnet_ids = var.rds_enabled ? (
    length(var.rds_subnet_ids) > 0 ? var.rds_subnet_ids : (
      var.rds_publicly_accessible ? [
        sort(tolist(data.aws_subnets.rds_autopick_az0_public[0].ids))[0],
        sort(tolist(data.aws_subnets.rds_autopick_az1_public[0].ids))[0],
        ] : [
        sort(tolist(data.aws_subnets.rds_autopick_az0_private[0].ids))[0],
        sort(tolist(data.aws_subnets.rds_autopick_az1_private[0].ids))[0],
      ]
    )
  ) : []

  rds_all_client_security_group_ids = concat(
    var.rds_allowed_security_group_ids,
    var.rds_enabled && var.rds_create_api_client_security_group ? [aws_security_group.api_rds_client[0].id] : [],
  )

  rds_ingress_rules = concat(
    [for c in var.rds_allowed_cidr_blocks : { cidr = c, sg = null }],
    [for s in local.rds_all_client_security_group_ids : { cidr = null, sg = s }],
  )
}

check "rds_subnets_when_enabled" {
  assert {
    condition     = !var.rds_enabled || length(local.rds_subnet_ids) >= 2
    error_message = "RDS needs at least 2 subnets. Set rds_subnet_ids to two subnet IDs in different AZs, or ensure the default VPC has subnets in the first two availability zones."
  }
}

data "aws_subnet" "rds_subnet_az" {
  for_each = var.rds_enabled ? toset(local.rds_subnet_ids) : toset([])
  id       = each.value
}

check "rds_subnet_multi_az" {
  assert {
    condition = (
      !var.rds_enabled
      || length(local.rds_subnet_ids) < 2
      || length(distinct([for id in local.rds_subnet_ids : data.aws_subnet.rds_subnet_az[id].availability_zone])) >= 2
    )
    error_message = "RDS subnet group must span at least 2 availability zones. Set rds_subnet_ids to one subnet per AZ (e.g. eu-west-1a + eu-west-1b), not two subnets in the same AZ."
  }
}

check "rds_autopick_subnets_exist" {
  assert {
    # use try(…, 0) so we never index [0] when that data source has count=0 (e.g. public RDS path vs private).
    condition = (
      !var.rds_enabled
      || length(var.rds_subnet_ids) > 0
      || (
        var.rds_publicly_accessible
        && try(length(data.aws_subnets.rds_autopick_az0_public[0].ids), 0) > 0
        && try(length(data.aws_subnets.rds_autopick_az1_public[0].ids), 0) > 0
      )
      || (
        !var.rds_publicly_accessible
        && try(length(data.aws_subnets.rds_autopick_az0_private[0].ids), 0) > 0
        && try(length(data.aws_subnets.rds_autopick_az1_private[0].ids), 0) > 0
      )
    )
    error_message = "For RDS subnet auto-pick: with rds_publicly_accessible=true, the default VPC needs map-public subnets in the first two AZs (or set rds_subnet_ids to two public subnets). With rds_publicly_accessible=false, ensure subnets exist in those AZs or set rds_subnet_ids."
  }
}

resource "random_password" "rds_master" {
  count   = var.rds_enabled ? 1 : 0
  length  = 24
  special = false
  # Explicit defaults (random provider 3.7+); avoids "update in-place" that can refresh .result and
  # break RDS + Secrets Manager URLs that embed this password.
  lower       = true
  upper       = true
  numeric     = true
  min_lower   = 0
  min_upper   = 0
  min_numeric = 0
  min_special = 0

  lifecycle {
    ignore_changes = [
      length,
      special,
      lower,
      upper,
      numeric,
      min_lower,
      min_upper,
      min_numeric,
      min_special,
    ]
  }
}

resource "aws_db_subnet_group" "main" {
  count = var.rds_enabled ? 1 : 0

  name       = substr("${var.project}-${var.environment}-rds", 0, 255)
  subnet_ids = local.rds_subnet_ids

  tags = {
    Project     = var.project
    Environment = var.environment
  }
}

resource "aws_security_group" "rds" {
  count = var.rds_enabled ? 1 : 0

  name_prefix = substr("${var.project}-${var.environment}-rds-pg-", 0, 90)
  description = "PostgreSQL from allowed CIDRs and security groups (see rds_allowed_* + managed api client SG)."
  vpc_id      = data.aws_vpc.default[0].id

  dynamic "ingress" {
    for_each = local.rds_ingress_rules
    content {
      description     = ingress.value.sg == null ? "PostgreSQL from CIDR" : "PostgreSQL from SG"
      from_port       = 5432
      to_port         = 5432
      protocol        = "tcp"
      cidr_blocks     = ingress.value.cidr != null ? [ingress.value.cidr] : null
      security_groups = ingress.value.sg != null ? [ingress.value.sg] : null
    }
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Project     = var.project
    Environment = var.environment
  }

  lifecycle {
    create_before_destroy = true
    # Description-only edits must not replace the SG (avoids duplicate name / broken partial applies).
    ignore_changes = [description]
  }
}

resource "aws_db_instance" "main" {
  count = var.rds_enabled ? 1 : 0

  identifier                 = substr("${var.project}-${var.environment}-pg", 0, 63)
  engine                     = "postgres"
  engine_version             = var.rds_engine_version
  instance_class             = var.rds_instance_class
  allocated_storage          = var.rds_allocated_storage
  max_allocated_storage      = var.rds_max_allocated_storage > 0 ? var.rds_max_allocated_storage : null
  storage_type               = "gp3"
  db_name                    = var.rds_database_name
  username                   = var.rds_master_username
  password                   = random_password.rds_master[0].result
  db_subnet_group_name       = aws_db_subnet_group.main[0].name
  vpc_security_group_ids     = [aws_security_group.rds[0].id]
  publicly_accessible        = var.rds_publicly_accessible
  skip_final_snapshot        = var.rds_skip_final_snapshot
  final_snapshot_identifier  = var.rds_skip_final_snapshot ? null : substr("${var.project}-${var.environment}-pg-final", 0, 255)
  backup_retention_period    = var.rds_backup_retention_days
  deletion_protection        = var.rds_deletion_protection
  auto_minor_version_upgrade = true

  tags = {
    Project     = var.project
    Environment = var.environment
  }
}
