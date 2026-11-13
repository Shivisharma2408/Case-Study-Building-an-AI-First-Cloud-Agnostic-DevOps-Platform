# Cluster adapter for a local kind cluster.
#
# kind clusters are Docker containers, so they are created by scripts/kind-up.sh
# (kind's own CLI) rather than Terraform. This module adopts the existing cluster:
# it installs the add-ons a managed cloud cluster would ship with and publishes
# the same `platform` contract as the eks/gke modules.

terraform {
  required_providers {
    helm = { source = "hashicorp/helm" }
  }
}

resource "helm_release" "metrics_server" {
  count = var.install_metrics_server ? 1 : 0

  name             = "metrics-server"
  repository       = "https://kubernetes-sigs.github.io/metrics-server/"
  chart            = "metrics-server"
  version          = var.metrics_server_chart_version
  namespace        = "kube-system"
  create_namespace = false
  wait             = true
  timeout          = 300

  values = [yamlencode({
    # kind kubelets use self-signed serving certs.
    args = ["--kubelet-insecure-tls"]
  })]
}
