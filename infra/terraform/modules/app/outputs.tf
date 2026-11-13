# Keep outputs free of database-derived values: callers index this module by
# environment to place the in-cluster database in the namespace, and any output
# depending on the database would create a dependency cycle.
output "namespace" {
  value = kubernetes_namespace_v1.this.metadata[0].name
}
