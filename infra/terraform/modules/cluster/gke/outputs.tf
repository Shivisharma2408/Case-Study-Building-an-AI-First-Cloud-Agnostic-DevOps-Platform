# --- The cluster contract (identical shape for kind / eks / gke) ---

output "name" {
  value = google_container_cluster.this.name
}

output "host" {
  value = "https://${google_container_cluster.this.endpoint}"
}

output "cluster_ca_certificate" {
  value = google_container_cluster.this.master_auth[0].cluster_ca_certificate
}

output "platform" {
  value = {
    cloud         = "gcp"
    storage_class = "standard-rwo"
    base_domain   = var.base_domain
    ingress_values = {
      controller = {
        service = {
          type        = "LoadBalancer"
          annotations = { "cloud.google.com/l4-rbs" = "enabled" }
        }
      }
    }
  }
}
