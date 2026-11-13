# Cloud-agnostic ingress controller. The only cloud-specific input is
# `platform.ingress_values` from the cluster module (hostPort on kind, NLB on EKS, L4 LB on GKE).
#
# NOTE: the ingress-nginx project is in end-of-life maintenance. This module is the single
# place to change when migrating to a Gateway API implementation; app charts only rely on
# the IngressClass name exported below.

terraform {
  required_providers {
    helm = { source = "hashicorp/helm" }
  }
}

locals {
  base_values = {
    controller = {
      ingressClassResource    = { name = var.ingress_class_name, default = true }
      ingressClass            = var.ingress_class_name
      allowSnippetAnnotations = false
      config = {
        "server-tokens"         = "false"
        "use-forwarded-headers" = "false"
        "proxy-body-size"       = "1m"
      }
      resources = {
        requests = { cpu = "50m", memory = "90Mi" }
        limits   = { memory = "256Mi" }
      }
      admissionWebhooks = { enabled = true }
      metrics           = { enabled = true }
    }
  }
}

resource "helm_release" "ingress_nginx" {
  name             = "ingress-nginx"
  repository       = "https://kubernetes.github.io/ingress-nginx"
  chart            = "ingress-nginx"
  version          = var.chart_version
  namespace        = var.namespace
  create_namespace = true
  wait             = true
  timeout          = 600

  # Later files win: platform-specific values override the shared baseline.
  values = [
    yamlencode(local.base_values),
    yamlencode(var.platform.ingress_values),
  ]
}
