provider "google" {
  project = var.project_id
  region  = var.region
}

data "google_client_config" "current" {}

# First apply on an empty project: `scripts/tf.sh <stack> apply -target=module.cluster`, then a full apply.
provider "kubernetes" {
  host                   = module.cluster.host
  cluster_ca_certificate = base64decode(module.cluster.cluster_ca_certificate)
  token                  = data.google_client_config.current.access_token
}

provider "helm" {
  kubernetes {
    host                   = module.cluster.host
    cluster_ca_certificate = base64decode(module.cluster.cluster_ca_certificate)
    token                  = data.google_client_config.current.access_token
  }
}
