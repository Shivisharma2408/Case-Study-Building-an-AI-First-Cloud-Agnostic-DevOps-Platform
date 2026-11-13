# Google Cloud SQL for PostgreSQL implementing the database contract (private IP only).
# DOCUMENTED, VALIDATED, NOT APPLIED (paid resource).
# Requires Private Service Access on `network` (a one-time VPC peering, usually in the landing zone).

terraform {
  required_providers {
    google = { source = "hashicorp/google" }
    random = { source = "hashicorp/random" }
  }
}

resource "random_password" "this" {
  length  = 32
  special = false
}

resource "google_sql_database_instance" "this" {
  name             = var.name
  project          = var.project_id
  region           = var.region
  database_version = var.database_version

  settings {
    tier              = var.tier
    availability_type = var.high_availability ? "REGIONAL" : "ZONAL"
    disk_type         = "PD_SSD"
    disk_size         = var.disk_size_gb
    disk_autoresize   = true
    user_labels       = var.labels

    ip_configuration {
      ipv4_enabled    = false
      private_network = var.network_id
      ssl_mode        = "ENCRYPTED_ONLY"
    }

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = var.high_availability
    }

    insights_config {
      query_insights_enabled = true
    }
  }

  deletion_protection = var.deletion_protection
}

resource "google_sql_database" "this" {
  name     = var.database_name
  project  = var.project_id
  instance = google_sql_database_instance.this.name
}

resource "google_sql_user" "this" {
  name     = var.username
  project  = var.project_id
  instance = google_sql_database_instance.this.name
  password = random_password.this.result
}
