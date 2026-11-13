variable "name" {
  type = string
}

variable "kubernetes_version" {
  type    = string
  default = "1.31"
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "public_api_endpoint" {
  type    = bool
  default = true
}

variable "public_api_cidrs" {
  description = "Restrict the public API endpoint (e.g. to your CI agents' egress IPs)."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "secrets_kms_key_arn" {
  description = "KMS key used for envelope encryption of Kubernetes Secrets."
  type        = string
}

variable "node_instance_types" {
  type    = list(string)
  default = ["t3.medium"]
}

variable "node_capacity_type" {
  description = "ON_DEMAND or SPOT (cost-sensitive environments)."
  type        = string
  default     = "ON_DEMAND"
  validation {
    condition     = contains(["ON_DEMAND", "SPOT"], var.node_capacity_type)
    error_message = "node_capacity_type must be ON_DEMAND or SPOT."
  }
}

variable "node_min_size" {
  type    = number
  default = 1
}

variable "node_max_size" {
  type    = number
  default = 3
}

variable "node_desired_size" {
  type    = number
  default = 2
}

variable "base_domain" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}
