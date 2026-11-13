# --- The cluster contract (identical shape for kind / eks / gke) ---

output "name" {
  value = var.cluster_name
}

output "platform" {
  description = "Cloud-specific knobs consumed by the cloud-agnostic modules."
  value = {
    cloud         = "local"
    storage_class = "standard" # kind's local-path provisioner
    base_domain   = var.base_domain
    # ingress-nginx on kind: bind node hostPorts (mapped to the host by kind) instead of a cloud LoadBalancer.
    ingress_values = {
      controller = {
        hostPort       = { enabled = true }
        service        = { type = "NodePort" }
        nodeSelector   = { "ingress-ready" = "true", "kubernetes.io/os" = "linux" }
        tolerations    = [{ key = "node-role.kubernetes.io/control-plane", operator = "Exists", effect = "NoSchedule" }]
        publishService = { enabled = false }
        extraArgs      = { "publish-status-address" = "localhost" }
        updateStrategy = { type = "RollingUpdate", rollingUpdate = { maxUnavailable = 1 } }
      }
    }
  }
}
