variable "cluster_name" {
  description = "Name of the kind cluster (created by scripts/kind-up.sh)."
  type        = string
}

variable "install_metrics_server" {
  description = "Install metrics-server so HorizontalPodAutoscalers have CPU metrics."
  type        = bool
  default     = true
}

variable "metrics_server_chart_version" {
  type    = string
  default = "3.12.2"
}

variable "base_domain" {
  description = "DNS suffix for app hosts. *.localhost resolves to 127.0.0.1 without /etc/hosts edits."
  type        = string
  default     = "ideaboard.localhost"
}
