variable "platform" {
  description = "The `platform` output of a cluster module."
  type = object({
    cloud          = string
    ingress_values = any
  })
}

variable "namespace" {
  type    = string
  default = "ingress-nginx"
}

variable "chart_version" {
  type    = string
  default = "4.12.0"
}

variable "ingress_class_name" {
  type    = string
  default = "nginx"
}
