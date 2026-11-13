# Google GKE implementation of the cluster contract.
# DOCUMENTED, VALIDATED (terraform validate), NOT APPLIED in this project: it creates paid resources.

terraform {
  required_providers {
    google = { source = "hashicorp/google" }
  }
}

resource "google_container_cluster" "this" {
  name     = var.name
  project  = var.project_id
  location = var.location

  network    = var.network
  subnetwork = var.subnetwork

  # Manage nodes with a separate pool so they can be changed without recreating the cluster.
  remove_default_node_pool = true
  initial_node_count       = 1

  release_channel {
    channel = var.release_channel
  }

  # Dataplane V2 (Cilium) enforces NetworkPolicy natively.
  datapath_provider = "ADVANCED_DATAPATH"

  ip_allocation_policy {}

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
    master_ipv4_cidr_block  = var.master_ipv4_cidr_block
  }

  deletion_protection = var.deletion_protection
  resource_labels     = var.labels
}

resource "google_container_node_pool" "default" {
  name     = "default"
  project  = var.project_id
  location = var.location
  cluster  = google_container_cluster.this.name

  autoscaling {
    min_node_count = var.node_min_count
    max_node_count = var.node_max_count
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }

  node_config {
    machine_type = var.machine_type
    spot         = var.spot
    oauth_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    labels       = var.labels
    workload_metadata_config {
      mode = "GKE_METADATA"
    }
    shielded_instance_config {
      enable_secure_boot = true
    }
  }
}
