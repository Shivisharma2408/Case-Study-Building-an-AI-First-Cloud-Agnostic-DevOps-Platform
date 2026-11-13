# Inputs specific to GCP. Common inputs: variables-common.tf.

variable "cloud" {
  type = string
  validation {
    condition     = var.cloud == "gcp"
    error_message = "This root (providers/gcp) only deploys cloud = \"gcp\"."
  }
}

variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "cluster_location" {
  description = "Region for a regional (HA) cluster, or a zone for a cheaper zonal one."
  type        = string
}

variable "network" {
  type = string
}

variable "subnetwork" {
  type = string
}

variable "network_id" {
  description = "VPC id with Private Service Access, for Cloud SQL private IP."
  type        = string
}

variable "machine_type" {
  type    = string
  default = "e2-standard-2"
}

variable "spot" {
  type    = bool
  default = false
}

variable "node_min_count" {
  type    = number
  default = 1
}

variable "node_max_count" {
  type    = number
  default = 3
}

variable "database_tier" {
  type    = string
  default = "db-f1-micro"
}

variable "labels" {
  type    = map(string)
  default = {}
}
