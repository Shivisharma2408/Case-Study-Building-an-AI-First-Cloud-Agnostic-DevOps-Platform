# Writes the database contract (modules/database/*) into the Secret the Helm chart
# reads via envFrom. Identical for in-cluster, RDS, Cloud SQL or external databases.

terraform {
  required_providers {
    kubernetes = { source = "hashicorp/kubernetes" }
  }
}

resource "kubernetes_secret_v1" "this" {
  metadata {
    name      = var.name
    namespace = var.namespace
    labels    = { "app.kubernetes.io/managed-by" = "terraform" }
  }
  data = {
    DB_HOST     = var.connection.host
    DB_PORT     = tostring(var.connection.port)
    DB_NAME     = var.connection.database
    DB_USER     = var.connection.username
    DB_PASSWORD = var.connection.password
    DB_SSLMODE  = var.connection.sslmode
  }
}
