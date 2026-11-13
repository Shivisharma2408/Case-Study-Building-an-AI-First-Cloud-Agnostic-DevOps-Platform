# Composition root for AWS: EKS + RDS. Same module graph as providers/local.
# NOT APPLIED in this project (paid resources) - validated with `terraform validate`.

locals {
  managed_dbs    = { for k, v in var.environments : k => v if v.database.mode == "managed" }
  in_cluster_dbs = { for k, v in var.environments : k => v if v.database.mode == "in_cluster" }
  external_dbs   = { for k, v in var.environments : k => v if v.database.mode == "external" }

  db_connections = merge(
    { for k, m in module.database_managed : k => m.connection },
    { for k, m in module.database_in_cluster : k => m.connection },
    {
      for k, v in local.external_dbs : k => {
        host     = v.database.external.host
        port     = v.database.external.port
        database = v.database.external.database
        username = v.database.external.username
        password = var.external_database_passwords[k]
        sslmode  = v.database.external.sslmode
      }
    },
  )
}

module "cluster" {
  source              = "../../modules/cluster/eks"
  name                = "${var.project}-${var.stack}"
  kubernetes_version  = var.kubernetes_version
  private_subnet_ids  = var.private_subnet_ids
  secrets_kms_key_arn = var.secrets_kms_key_arn
  public_api_cidrs    = var.public_api_cidrs
  node_instance_types = var.node_instance_types
  node_capacity_type  = var.node_capacity_type
  node_min_size       = var.node_min_size
  node_max_size       = var.node_max_size
  node_desired_size   = var.node_desired_size
  base_domain         = var.base_domain
}

module "ingress" {
  source        = "../../modules/ingress"
  platform      = module.cluster.platform
  chart_version = var.ingress_chart_version
}

module "database_managed" {
  source   = "../../modules/database/rds"
  for_each = local.managed_dbs

  name                = "${var.project}-${each.key}"
  vpc_id              = var.vpc_id
  subnet_ids          = var.private_subnet_ids
  allowed_cidrs       = var.cluster_cidrs
  instance_class      = var.database_instance_class
  multi_az            = each.value.database.high_availability
  deletion_protection = each.value.database.high_availability
}

module "app" {
  source   = "../../modules/app"
  for_each = var.environments

  namespace          = each.key
  pod_security_level = each.value.pod_security_level
  quota              = each.value.quota
  labels             = { "app.kubernetes.io/part-of" = var.project }
}

module "database_in_cluster" {
  source   = "../../modules/database/in-cluster"
  for_each = local.in_cluster_dbs

  namespace     = module.app[each.key].namespace
  storage_class = module.cluster.platform.storage_class
  storage_size  = each.value.database.storage_size
}

module "database_secret" {
  source   = "../../modules/app/database-secret"
  for_each = var.environments

  namespace  = module.app[each.key].namespace
  connection = local.db_connections[each.key]
}
