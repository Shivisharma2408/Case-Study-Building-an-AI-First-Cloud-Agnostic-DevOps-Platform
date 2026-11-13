# Cloud-agnostic application landing zone: namespace (Pod Security "restricted"),
# quota and default container limits. The DB credentials Secret the chart consumes
# is written by ./database-secret once the database exists (namespace -> database -> secret).
#
# Terraform owns the platform; the pipeline owns application releases (helm upgrade/rollback).
# Keeping releases out of Terraform state avoids drift every time CI deploys a new image tag.

terraform {
  required_providers {
    kubernetes = { source = "hashicorp/kubernetes" }
  }
}

resource "kubernetes_namespace_v1" "this" {
  metadata {
    name = var.namespace
    labels = merge(var.labels, {
      "pod-security.kubernetes.io/enforce" = var.pod_security_level
      "pod-security.kubernetes.io/warn"    = "restricted"
      "idea-board/environment"             = var.namespace
    })
  }
}

resource "kubernetes_resource_quota_v1" "this" {
  metadata {
    name      = "default"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
  }
  spec {
    hard = {
      "requests.cpu"           = var.quota.requests_cpu
      "requests.memory"        = var.quota.requests_memory
      "limits.cpu"             = var.quota.limits_cpu
      "limits.memory"          = var.quota.limits_memory
      "pods"                   = tostring(var.quota.pods)
      "persistentvolumeclaims" = "5"
      "services.loadbalancers" = "0" # traffic enters only through the shared ingress
    }
  }
}

resource "kubernetes_limit_range_v1" "this" {
  metadata {
    name      = "default"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
  }
  spec {
    limit {
      type            = "Container"
      default_request = { cpu = "50m", memory = "64Mi" }
      default         = { cpu = "250m", memory = "256Mi" }
    }
  }
}
