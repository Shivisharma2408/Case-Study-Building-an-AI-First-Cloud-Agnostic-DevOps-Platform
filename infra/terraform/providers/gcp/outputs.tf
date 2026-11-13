output "cloud" {
  value = module.cluster.platform.cloud
}

output "cluster_name" {
  value = module.cluster.name
}

output "namespaces" {
  value = [for m in module.app : m.namespace]
}

output "app_urls" {
  description = "Point DNS for these hosts at the ingress load balancer (kubectl -n ingress-nginx get svc)."
  value = {
    for k, v in var.environments :
    k => "https://${coalesce(v.hostname, "${k}.${var.base_domain}")}/"
  }
}
