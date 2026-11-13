provider "aws" {
  region = var.region
  default_tags {
    tags = merge(var.tags, { project = var.project, stack = var.stack, managed-by = "terraform" })
  }
}

# The Kubernetes/Helm providers authenticate with short-lived tokens from the AWS CLI.
# First apply on an empty account: `scripts/tf.sh <stack> apply -target=module.cluster`, then a full apply.
provider "kubernetes" {
  host                   = module.cluster.host
  cluster_ca_certificate = base64decode(module.cluster.cluster_ca_certificate)
  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args        = ["eks", "get-token", "--cluster-name", module.cluster.name, "--region", var.region]
  }
}

provider "helm" {
  kubernetes {
    host                   = module.cluster.host
    cluster_ca_certificate = base64decode(module.cluster.cluster_ca_certificate)
    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args        = ["eks", "get-token", "--cluster-name", module.cluster.name, "--region", var.region]
    }
  }
}
