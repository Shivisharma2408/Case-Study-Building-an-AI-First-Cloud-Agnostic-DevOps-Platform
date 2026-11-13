# Inputs specific to the local (kind) provider. Common inputs: variables-common.tf.

variable "cloud" {
  type = string
  validation {
    condition     = var.cloud == "local"
    error_message = "This root (providers/local) only deploys cloud = \"local\"."
  }
}

variable "kubeconfig_path" {
  type    = string
  default = "~/.kube/config"
}

variable "kube_context" {
  description = "kubectl context of the kind cluster (kind-<cluster name>)."
  type        = string
}

variable "kind_cluster_name" {
  type = string
}

variable "ingress_http_port" {
  description = "Host port kind maps to the ingress controller (used for output URLs only)."
  type        = number
  default     = 8080
}
