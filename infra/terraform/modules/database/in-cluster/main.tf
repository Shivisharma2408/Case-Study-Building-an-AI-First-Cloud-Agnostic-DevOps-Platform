# In-cluster PostgreSQL (StatefulSet + PVC) implementing the database contract.
# Used for the local kind platform; a managed database (rds / cloudsql) is a drop-in
# replacement because consumers only see the `connection` output.

terraform {
  required_providers {
    kubernetes = { source = "hashicorp/kubernetes" }
    random     = { source = "hashicorp/random" }
  }
}

locals {
  labels = {
    "app.kubernetes.io/name"       = "postgres"
    "app.kubernetes.io/instance"   = var.name
    "app.kubernetes.io/component"  = "database"
    "app.kubernetes.io/managed-by" = "terraform"
  }
  selector = {
    "app.kubernetes.io/name"     = "postgres"
    "app.kubernetes.io/instance" = var.name
  }
}

resource "random_password" "this" {
  length  = 32
  special = false
}

resource "kubernetes_secret_v1" "credentials" {
  metadata {
    name      = "${var.name}-credentials"
    namespace = var.namespace
    labels    = local.labels
  }
  data = {
    POSTGRES_DB       = var.database_name
    POSTGRES_USER     = var.username
    POSTGRES_PASSWORD = random_password.this.result
  }
}

resource "kubernetes_service_v1" "this" {
  metadata {
    name      = var.name
    namespace = var.namespace
    labels    = local.labels
  }
  spec {
    selector = local.selector
    port {
      name        = "postgres"
      port        = 5432
      target_port = "postgres"
    }
  }
}

resource "kubernetes_stateful_set_v1" "this" {
  metadata {
    name      = var.name
    namespace = var.namespace
    labels    = local.labels
  }

  wait_for_rollout = true

  spec {
    service_name = kubernetes_service_v1.this.metadata[0].name
    replicas     = 1

    selector {
      match_labels = local.selector
    }

    template {
      metadata {
        labels = local.labels
      }
      spec {
        automount_service_account_token = false
        security_context {
          run_as_non_root = true
          run_as_user     = 70 # postgres user in the alpine image
          run_as_group    = 70
          fs_group        = 70
          seccomp_profile {
            type = "RuntimeDefault"
          }
        }

        container {
          name  = "postgres"
          image = var.image

          port {
            name           = "postgres"
            container_port = 5432
          }

          env {
            name  = "PGDATA"
            value = "/var/lib/postgresql/data/pgdata"
          }
          env_from {
            secret_ref {
              name = kubernetes_secret_v1.credentials.metadata[0].name
            }
          }

          readiness_probe {
            exec {
              command = ["sh", "-c", "pg_isready -U \"$POSTGRES_USER\" -d \"$POSTGRES_DB\" -h 127.0.0.1"]
            }
            period_seconds = 5
          }
          liveness_probe {
            exec {
              command = ["sh", "-c", "pg_isready -U \"$POSTGRES_USER\" -d \"$POSTGRES_DB\" -h 127.0.0.1"]
            }
            initial_delay_seconds = 30
            period_seconds        = 10
            failure_threshold     = 6
          }

          resources {
            requests = { cpu = var.resources.cpu_request, memory = var.resources.memory_request }
            limits   = { cpu = var.resources.cpu_limit, memory = var.resources.memory_limit }
          }

          security_context {
            allow_privilege_escalation = false
            read_only_root_filesystem  = true
            capabilities {
              drop = ["ALL"]
            }
          }

          volume_mount {
            name       = "data"
            mount_path = "/var/lib/postgresql/data"
          }
          volume_mount {
            name       = "run"
            mount_path = "/var/run/postgresql"
          }
          volume_mount {
            name       = "tmp"
            mount_path = "/tmp"
          }
        }

        volume {
          name = "run"
          empty_dir {}
        }
        volume {
          name = "tmp"
          empty_dir {}
        }
      }
    }

    volume_claim_template {
      metadata {
        name = "data"
      }
      spec {
        access_modes       = ["ReadWriteOnce"]
        storage_class_name = var.storage_class
        resources {
          requests = { storage = var.storage_size }
        }
      }
    }
  }
}

# Only the application backend may reach the database; the database itself needs no egress.
resource "kubernetes_network_policy_v1" "this" {
  metadata {
    name      = "${var.name}-allow-clients"
    namespace = var.namespace
    labels    = local.labels
  }
  spec {
    pod_selector {
      match_labels = local.selector
    }
    policy_types = ["Ingress", "Egress"]
    ingress {
      from {
        pod_selector {
          match_labels = var.client_pod_labels
        }
      }
      ports {
        protocol = "TCP"
        port     = "5432"
      }
    }
  }
}
