# ---------------------------------------------------------------------------
# CLOUD-AGNOSTIC INPUTS - this file is byte-identical in providers/{local,aws,gcp}.
# scripts/stages/lint_test.sh fails the pipeline if the copies drift.
# ---------------------------------------------------------------------------

variable "project" {
  description = "Prefix for cloud resource names."
  type        = string
  default     = "idea-board"
}

variable "stack" {
  description = "Name of this Terraform stack (environments/<stack>)."
  type        = string
}

variable "base_domain" {
  description = "Apps are served at <env>.<base_domain>, production at <base_domain>."
  type        = string
}

variable "ingress_chart_version" {
  type    = string
  default = "4.12.0"
}

variable "environments" {
  description = "Application environments (namespaces) hosted by this stack."
  type = map(object({
    hostname           = optional(string)
    pod_security_level = optional(string, "restricted")
    quota = optional(object({
      requests_cpu    = string
      requests_memory = string
      limits_cpu      = string
      limits_memory   = string
      pods            = number
      }), {
      requests_cpu    = "2"
      requests_memory = "2Gi"
      limits_cpu      = "4"
      limits_memory   = "4Gi"
      pods            = 20
    })
    database = optional(object({
      # in_cluster: PostgreSQL StatefulSet | managed: RDS / Cloud SQL | external: bring your own
      mode              = optional(string, "in_cluster")
      storage_size      = optional(string, "1Gi")
      high_availability = optional(bool, false)
      external = optional(object({
        host     = string
        port     = optional(number, 5432)
        database = optional(string, "ideas")
        username = string
        sslmode  = optional(string, "require")
      }))
    }), {})
  }))

  validation {
    condition     = alltrue([for e in values(var.environments) : contains(["in_cluster", "managed", "external"], e.database.mode)])
    error_message = "database.mode must be one of in_cluster, managed, external."
  }
  validation {
    condition     = alltrue([for e in values(var.environments) : e.database.mode != "external" || e.database.external != null])
    error_message = "database.external must be set when database.mode = \"external\"."
  }
}

variable "external_database_passwords" {
  description = "Passwords for mode=external databases, keyed by environment. Pass via TF_VAR_external_database_passwords, never in tfvars."
  type        = map(string)
  sensitive   = true
  default     = {}
}
