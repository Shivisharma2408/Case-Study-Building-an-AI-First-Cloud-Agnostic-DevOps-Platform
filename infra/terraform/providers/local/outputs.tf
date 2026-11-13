output "cloud" {
  value = module.cluster.platform.cloud
}

output "namespaces" {
  value = [for m in module.app : m.namespace]
}

output "app_urls" {
  description = "Where each environment is served (through ingress-nginx on the kind host port)."
  value = {
    for k, v in var.environments :
    k => "http://${coalesce(v.hostname, "${k}.${var.base_domain}")}:${var.ingress_http_port}/"
  }
}
