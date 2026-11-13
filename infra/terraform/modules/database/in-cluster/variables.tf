variable "namespace" {
  type = string
}

variable "name" {
  type    = string
  default = "postgres"
}

variable "image" {
  type    = string
  default = "postgres:16.6-alpine3.21"
}

variable "database_name" {
  type    = string
  default = "ideas"
}

variable "username" {
  type    = string
  default = "ideas"
}

variable "storage_class" {
  type = string
}

variable "storage_size" {
  type    = string
  default = "1Gi"
}

variable "resources" {
  type = object({
    cpu_request    = string
    memory_request = string
    cpu_limit      = string
    memory_limit   = string
  })
  default = {
    cpu_request    = "50m"
    memory_request = "128Mi"
    cpu_limit      = "500m"
    memory_limit   = "512Mi"
  }
}

variable "client_pod_labels" {
  description = "Labels of the pods allowed to connect (the app backend)."
  type        = map(string)
  default = {
    "app.kubernetes.io/name"      = "idea-board"
    "app.kubernetes.io/component" = "backend"
  }
}
