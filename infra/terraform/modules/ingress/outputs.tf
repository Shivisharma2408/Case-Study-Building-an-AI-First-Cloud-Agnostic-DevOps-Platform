output "namespace" {
  value = helm_release.ingress_nginx.namespace
}

output "ingress_class_name" {
  value = var.ingress_class_name
}
