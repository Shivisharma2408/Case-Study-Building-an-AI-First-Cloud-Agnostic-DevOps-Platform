# --- The database contract (identical shape for in-cluster / rds / cloudsql) ---
output "connection" {
  sensitive = true
  value = {
    host     = aws_db_instance.this.address
    port     = aws_db_instance.this.port
    database = var.database_name
    username = var.username
    password = random_password.this.result
    sslmode  = "require"
  }
}
