variable "namespace" {
  type = string
  validation {
    condition     = can(regex("^[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?$", var.namespace))
    error_message = "namespace must be a valid DNS-1123 label."
  }
}

variable "labels" {
  type    = map(string)
  default = {}
}

variable "pod_security_level" {
  type    = string
  default = "restricted"
  validation {
    condition     = contains(["privileged", "baseline", "restricted"], var.pod_security_level)
    error_message = "pod_security_level must be privileged, baseline or restricted."
  }
}

variable "quota" {
  type = object({
    requests_cpu    = string
    requests_memory = string
    limits_cpu      = string
    limits_memory   = string
    pods            = number
  })
}
