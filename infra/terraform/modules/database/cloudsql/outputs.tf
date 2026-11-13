# --- The database contract (identical shape for in-cluster / rds / cloudsql) ---
output "connection" {
  sensitive = true
  value = {
    host     = google_sql_database_instance.this.private_ip_address
    port     = 5432
    database = google_sql_database.this.name
    username = google_sql_user.this.name
    password = random_password.this.result
    sslmode  = "require"
  }
}
