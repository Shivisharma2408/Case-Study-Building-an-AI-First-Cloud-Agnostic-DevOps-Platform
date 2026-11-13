# Composition root for GCP: GKE + Cloud SQL. Same module graph as providers/local.
# NOT APPLIED in this project (paid resources) - validated with `terraform validate`.

locals {
  labels         = merge(var.labels, { project = var.project, stack = var.stack, managed-by = "terraform" })
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
  source         = "../../modules/cluster/gke"
  name           = "${var.project}-${var.stack}"
  project_id     = var.project_id
  location       = var.cluster_location
  network        = var.network
  subnetwork     = var.subnetwork
  machine_type   = var.machine_type
  spot           = var.spot
  node_min_count = var.node_min_count
  node_max_count = var.node_max_count
  base_domain    = var.base_domain
  labels         = local.labels
}

module "ingress" {
  source        = "../../modules/ingress"
  platform      = module.cluster.platform
  chart_version = var.ingress_chart_version
}

module "database_managed" {
  source   = "../../modules/database/cloudsql"
  for_each = local.managed_dbs

  name                = "${var.project}-${each.key}"
  project_id          = var.project_id
  region              = var.region
  network_id          = var.network_id
  tier                = var.database_tier
  high_availability   = each.value.database.high_availability
  deletion_protection = each.value.database.high_availability
  labels              = local.labels
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
