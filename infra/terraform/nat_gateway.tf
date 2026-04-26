# Single NAT gateway so App Runner VPC egress (same subnets as RDS) can reach the internet
# (OpenRouter HTTPS, etc.). Adds 0.0.0.0/0 -> NAT only on route tables that do not already
# have an IPv4 default route (typical private subnets). If your tables use 0.0.0.0/0 -> IGW
# (common default VPC), use the output replace-route commands once after apply.

locals {
  apprunner_nat_enabled = (
    var.apprunner_enabled &&
    var.rds_enabled &&
    var.apprunner_manage_nat_gateway
  )

  apprunner_nat_use_dedicated_public = (
    local.apprunner_nat_enabled &&
    var.apprunner_nat_create_dedicated_public_subnet &&
    trimspace(var.apprunner_nat_dedicated_subnet_ipv4_cidr) != ""
  )
}

# NAT sits in a public subnet; the VPC must have an Internet Gateway (default VPC does).
data "aws_internet_gateway" "apprunner_nat_vpc" {
  count = local.apprunner_nat_enabled ? 1 : 0
  filter {
    name   = "attachment.vpc-id"
    values = [data.aws_vpc.default[0].id]
  }
}

# Dedicated /28+ public subnet for NAT only (IGW default route). Avoids NAT-in-NAT-only-RT hairpin.
data "aws_subnet" "apprunner_nat_rds_subnet_for_az" {
  count = local.apprunner_nat_use_dedicated_public ? 1 : 0
  id    = local.rds_subnet_ids[0]
}

resource "aws_subnet" "apprunner_nat_public_dedicated" {
  count = local.apprunner_nat_use_dedicated_public ? 1 : 0

  vpc_id                  = data.aws_vpc.default[0].id
  cidr_block              = trimspace(var.apprunner_nat_dedicated_subnet_ipv4_cidr)
  availability_zone       = data.aws_subnet.apprunner_nat_rds_subnet_for_az[0].availability_zone
  map_public_ip_on_launch = true

  tags = {
    Project     = var.project
    Environment = var.environment
    Name        = "${var.project}-${var.environment}-nat-public"
  }
}

resource "aws_route_table" "apprunner_nat_public_dedicated" {
  count  = local.apprunner_nat_use_dedicated_public ? 1 : 0
  vpc_id = data.aws_vpc.default[0].id

  tags = {
    Project     = var.project
    Environment = var.environment
    Name        = "${var.project}-${var.environment}-nat-public-rt"
  }
}

resource "aws_route" "apprunner_nat_public_dedicated_igw" {
  count = local.apprunner_nat_use_dedicated_public ? 1 : 0

  route_table_id         = aws_route_table.apprunner_nat_public_dedicated[0].id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = data.aws_internet_gateway.apprunner_nat_vpc[0].id

  depends_on = [data.aws_internet_gateway.apprunner_nat_vpc]
}

resource "aws_route_table_association" "apprunner_nat_public_dedicated" {
  count = local.apprunner_nat_use_dedicated_public ? 1 : 0

  subnet_id      = aws_subnet.apprunner_nat_public_dedicated[0].id
  route_table_id = aws_route_table.apprunner_nat_public_dedicated[0].id
}

data "aws_subnet" "apprunner_nat_placement" {
  count = local.apprunner_nat_enabled ? 1 : 0
  id = (
    local.apprunner_nat_use_dedicated_public
    ? aws_subnet.apprunner_nat_public_dedicated[0].id
    : var.apprunner_nat_public_subnet_id
  )
}

check "apprunner_nat_placement_vpc" {
  assert {
    # Dedicated path: new subnet id is unknown at plan; use RDS subnet VPC (same vpc_id we create into).
    condition = (
      !local.apprunner_nat_enabled
      ? true
      : (
        local.apprunner_nat_use_dedicated_public
        ? data.aws_subnet.apprunner_nat_rds_subnet_for_az[0].vpc_id == data.aws_vpc.default[0].id
        : data.aws_subnet.apprunner_nat_placement[0].vpc_id == data.aws_vpc.default[0].id
      )
    )
    error_message = "NAT placement must be in the same VPC as RDS (default VPC when rds_subnet_ids is empty)."
  }
}

# NAT must not rely on a subnet whose only default internet path is itself (NAT hairpin).
check "apprunner_nat_public_subnet_or_dedicated" {
  assert {
    condition = (
      !local.apprunner_nat_enabled
      || local.apprunner_nat_use_dedicated_public
      || trimspace(var.apprunner_nat_public_subnet_id) != ""
    )
    error_message = "Choose one: (A) apprunner_nat_create_dedicated_public_subnet = true and set apprunner_nat_dedicated_subnet_ipv4_cidr to an unused /28 in the VPC, or (B) set apprunner_nat_public_subnet_id to an existing public subnet (0.0.0.0/0 -> IGW) that is not stuck behind NAT-only routing."
  }
}

resource "aws_eip" "apprunner_nat" {
  count  = local.apprunner_nat_enabled ? 1 : 0
  domain = "vpc"

  tags = {
    Project     = var.project
    Environment = var.environment
    Name        = "${var.project}-${var.environment}-nat"
  }

  depends_on = [data.aws_internet_gateway.apprunner_nat_vpc]
}

resource "aws_nat_gateway" "apprunner_nat" {
  count = local.apprunner_nat_enabled ? 1 : 0

  allocation_id = aws_eip.apprunner_nat[0].id
  subnet_id     = data.aws_subnet.apprunner_nat_placement[0].id

  tags = {
    Project     = var.project
    Environment = var.environment
    Name        = "${var.project}-${var.environment}-nat"
  }

  depends_on = [data.aws_internet_gateway.apprunner_nat_vpc]
}

# Subnets on the VPC "main" route table have no association.subnet-id row in EC2, so
# data.aws_route_table { subnet_id = ... } returns no results. Look up explicit associations
# first, then fall back to the main route table for the VPC.
data "aws_route_tables" "apprunner_explicit_subnet_assoc" {
  for_each = local.apprunner_nat_enabled ? toset(local.rds_subnet_ids) : toset([])
  vpc_id   = data.aws_vpc.default[0].id
  filter {
    name   = "association.subnet-id"
    values = [each.value]
  }
}

data "aws_route_table" "apprunner_vpc_main" {
  count  = local.apprunner_nat_enabled ? 1 : 0
  vpc_id = data.aws_vpc.default[0].id
  filter {
    name   = "association.main"
    values = ["true"]
  }
}

locals {
  apprunner_subnet_to_route_table_id = local.apprunner_nat_enabled ? {
    for sid in local.rds_subnet_ids : sid => (
      length(data.aws_route_tables.apprunner_explicit_subnet_assoc[sid].ids) > 0
      ? element(sort(tolist(data.aws_route_tables.apprunner_explicit_subnet_assoc[sid].ids)), 0)
      : data.aws_route_table.apprunner_vpc_main[0].id
    )
  } : {}

  apprunner_connector_route_table_ids = local.apprunner_nat_enabled ? distinct([
    for sid in local.rds_subnet_ids : local.apprunner_subnet_to_route_table_id[sid]
  ]) : []
}

data "aws_route_table" "apprunner_connector_detail" {
  for_each       = local.apprunner_nat_enabled ? toset(local.apprunner_connector_route_table_ids) : toset([])
  route_table_id = each.value
}

locals {
  # Route tables with no 0.0.0.0/0 at all — safe to create a managed aws_route.
  apprunner_nat_route_table_ids_ipv4_default_absent = local.apprunner_nat_enabled ? toset([
    for rtb_id in local.apprunner_connector_route_table_ids : rtb_id
    if length([
      for r in data.aws_route_table.apprunner_connector_detail[rtb_id].routes :
      r if try(r.cidr_block, null) != null && r.cidr_block == "0.0.0.0/0"
    ]) == 0
  ]) : toset([])

  # Route tables that already send 0.0.0.0/0 to an Internet Gateway — Terraform cannot create
  # a second default route; use output commands (replace-route) after NAT exists.
  apprunner_nat_route_table_ids_ipv4_default_igw = local.apprunner_nat_enabled ? toset([
    for rtb_id in local.apprunner_connector_route_table_ids : rtb_id
    if length([
      for r in data.aws_route_table.apprunner_connector_detail[rtb_id].routes :
      r if try(r.cidr_block, null) != null && r.cidr_block == "0.0.0.0/0" && try(r.gateway_id, "") != ""
    ]) > 0
  ]) : toset([])
}

resource "aws_route" "apprunner_nat_ipv4_default" {
  for_each = (
    local.apprunner_nat_enabled && var.apprunner_manage_nat_ipv4_routes
    ? local.apprunner_nat_route_table_ids_ipv4_default_absent
    : toset([])
  )

  route_table_id         = each.value
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.apprunner_nat[0].id

  depends_on = [aws_nat_gateway.apprunner_nat]
}

# Default VPC subnets often have 0.0.0.0/0 -> IGW; App Runner VPC egress needs NAT. aws_route cannot adopt
# an existing IGW route in one step, so replace in place via AWS CLI (same as output replace-route commands).
resource "null_resource" "apprunner_replace_igw_default_route_to_nat" {
  count = (
    local.apprunner_nat_enabled &&
    var.apprunner_manage_nat_ipv4_routes &&
    var.apprunner_nat_cli_replace_igw_default_route &&
    length(local.apprunner_nat_route_table_ids_ipv4_default_igw) > 0
  ) ? 1 : 0

  triggers = {
    nat_id = aws_nat_gateway.apprunner_nat[0].id
    rtbs   = join(",", sort(tolist(local.apprunner_nat_route_table_ids_ipv4_default_igw)))
  }

  provisioner "local-exec" {
    command = join(" && ", [
      for rtb_id in sort(tolist(local.apprunner_nat_route_table_ids_ipv4_default_igw)) :
      "aws ec2 replace-route --region ${var.aws_region} --route-table-id ${rtb_id} --destination-cidr-block 0.0.0.0/0 --nat-gateway-id ${aws_nat_gateway.apprunner_nat[0].id}"
    ])
  }

  depends_on = [
    aws_nat_gateway.apprunner_nat,
    aws_route.apprunner_nat_ipv4_default,
  ]
}
