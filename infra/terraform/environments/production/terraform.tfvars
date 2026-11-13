# Stack "production" on a real cloud. DOCUMENTED, NOT APPLIED (paid resources).
# Switch clouds by changing `cloud` below ("aws" <-> "gcp"); provider details live in <cloud>.tfvars.
#   scripts/tf.sh production plan

cloud       = "aws"
stack       = "production"
base_domain = "ideaboard.example.com"

environments = {
  production = {
    hostname = "ideaboard.example.com"
    quota = {
      requests_cpu    = "4"
      requests_memory = "8Gi"
      limits_cpu      = "8"
      limits_memory   = "16Gi"
      pods            = 50
    }
    # High availability: Multi-AZ / regional managed DB with deletion protection.
    database = { mode = "managed", high_availability = true }
  }
}
