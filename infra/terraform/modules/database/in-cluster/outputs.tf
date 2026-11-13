# --- The database contract (identical shape for in-cluster / rds / cloudsql) ---
output "connection" {
  sensitive = true
  value = {
    host     = "${kubernetes_service_v1.this.metadata[0].name}.${var.namespace}.svc.cluster.local"
    port     = 5432
    database = var.database_name
    username = var.username
    password = random_password.this.result
    sslmode  = "disable" # traffic never leaves the cluster network; NetworkPolicy restricts clients
  }
  # Consumers must not connect before the server is actually running.
  depends_on = [kubernetes_stateful_set_v1.this]
}
