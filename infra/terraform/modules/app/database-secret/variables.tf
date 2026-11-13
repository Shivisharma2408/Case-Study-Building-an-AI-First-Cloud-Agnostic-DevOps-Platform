variable "namespace" {
  type = string
}

variable "name" {
  type    = string
  default = "idea-board-db"
}

variable "connection" {
  description = "Database contract: the `connection` output of a modules/database/* implementation."
  sensitive   = true
  type = object({
    host     = string
    port     = number
    database = string
    username = string
    password = string
    sslmode  = string
  })
}
