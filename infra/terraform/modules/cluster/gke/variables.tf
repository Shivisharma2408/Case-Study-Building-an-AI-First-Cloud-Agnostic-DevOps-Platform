variable "name" {
  type = string
}

variable "project_id" {
  type = string
}

variable "location" {
  description = "Region (regional, HA control plane) or zone (cheaper, zonal)."
  type        = string
}

variable "network" {
  type = string
}

variable "subnetwork" {
  type = string
}

variable "release_channel" {
  type    = string
  default = "REGULAR"
}

variable "master_ipv4_cidr_block" {
  type    = string
  default = "172.16.0.0/28"
}

variable "machine_type" {
  type    = string
  default = "e2-standard-2"
}

variable "spot" {
  description = "Use Spot VMs (cost-sensitive environments)."
  type        = bool
  default     = false
}

variable "node_min_count" {
  type    = number
  default = 1
}

variable "node_max_count" {
  type    = number
  default = 3
}

variable "deletion_protection" {
  type    = bool
  default = true
}

variable "base_domain" {
  type = string
}

variable "labels" {
  type    = map(string)
  default = {}
}
