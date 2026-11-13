# Stack "staging" on a real cloud. DOCUMENTED, NOT APPLIED (paid resources).
# Switch clouds by changing `cloud` below ("aws" <-> "gcp"); provider details live in <cloud>.tfvars.
#   scripts/tf.sh staging plan

cloud       = "aws"
stack       = "staging"
base_domain = "staging.ideaboard.example.com"

environments = {
  staging = {
    hostname = "staging.ideaboard.example.com"
    # Cost-sensitive: managed DB, single AZ, no deletion protection.
    database = { mode = "managed", high_availability = false }
  }
}
