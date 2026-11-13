# Composition root for the LOCAL provider: kind cluster + in-cluster PostgreSQL.
# Same module graph as providers/aws and providers/gcp; only the cluster and
# database implementations differ.

locals {
  in_cluster_dbs = { for k, v in var.environments : k => v if v.database.mode == "in_cluster" }
  external_dbs   = { for k, v in var.environments : k => v if v.database.mode == "external" }

  db_connections = merge(
    { for k, m in module.database : k => m.connection },
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

resource "terraform_data" "guardrails" {
  lifecycle {
    precondition {
      condition     = alltrue([for e in values(var.environments) : e.database.mode != "managed"])
      error_message = "The local provider has no managed database service; use in_cluster or external."
    }
  }
}

module "cluster" {
  source       = "../../modules/cluster/kind"
  cluster_name = var.kind_cluster_name
  base_domain  = var.base_domain
}

module "ingress" {
  source        = "../../modules/ingress"
  platform      = module.cluster.platform
  chart_version = var.ingress_chart_version
}

module "app" {
  source   = "../../modules/app"
  for_each = var.environments

  namespace          = each.key
  pod_security_level = each.value.pod_security_level
  quota              = each.value.quota
  labels             = { "app.kubernetes.io/part-of" = var.project }
}

module "database" {
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
