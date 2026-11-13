# Stack "local": one kind cluster hosting BOTH application environments
# (namespaces `staging` and `production`) - the local stand-in for "two clouds".
# This is the stack that is actually applied:  scripts/tf.sh local apply

cloud       = "local" # <- the only line that selects the provider root (providers/<cloud>)
stack       = "local"
base_domain = "ideaboard.localhost"

environments = {
  staging = {
    quota = {
      requests_cpu    = "1"
      requests_memory = "1Gi"
      limits_cpu      = "3"
      limits_memory   = "3Gi"
      pods            = 15
    }
    database = { mode = "in_cluster", storage_size = "1Gi" }
  }

  production = {
    hostname = "ideaboard.localhost"
    database = { mode = "in_cluster", storage_size = "2Gi" }
    # Swap in any reachable PostgreSQL without touching the app:
    # database = {
    #   mode     = "external"
    #   external = { host = "db.example.internal", username = "ideas", sslmode = "require" }
    # }
    # ...and export TF_VAR_external_database_passwords='{"production":"..."}'
  }
}
