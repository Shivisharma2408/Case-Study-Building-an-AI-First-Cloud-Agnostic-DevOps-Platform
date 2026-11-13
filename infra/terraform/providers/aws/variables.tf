# Inputs specific to AWS. Common inputs: variables-common.tf.

variable "cloud" {
  type = string
  validation {
    condition     = var.cloud == "aws"
    error_message = "This root (providers/aws) only deploys cloud = \"aws\"."
  }
}

variable "region" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "cluster_cidrs" {
  description = "Node/pod CIDRs allowed to reach RDS."
  type        = list(string)
}

variable "secrets_kms_key_arn" {
  type = string
}

variable "public_api_cidrs" {
  description = "CIDRs allowed to reach the public EKS API endpoint."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "kubernetes_version" {
  type    = string
  default = "1.31"
}

variable "node_instance_types" {
  type    = list(string)
  default = ["t3.medium"]
}

variable "node_capacity_type" {
  type    = string
  default = "ON_DEMAND"
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

variable "database_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "tags" {
  type    = map(string)
  default = {}
}
