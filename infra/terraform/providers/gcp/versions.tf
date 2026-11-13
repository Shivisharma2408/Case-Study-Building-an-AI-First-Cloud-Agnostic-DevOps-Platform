terraform {
  required_version = ">= 1.6.0"

  required_providers {
    google     = { source = "hashicorp/google", version = "~> 6.14" }
    kubernetes = { source = "hashicorp/kubernetes", version = "~> 2.35" }
    helm       = { source = "hashicorp/helm", version = "~> 2.17" }
    random     = { source = "hashicorp/random", version = "~> 3.6" }
  }

  # Partial config; supply bucket/prefix with -backend-config (see README).
  backend "gcs" {}
}
