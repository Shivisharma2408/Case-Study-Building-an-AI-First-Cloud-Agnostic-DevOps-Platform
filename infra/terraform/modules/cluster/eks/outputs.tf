# --- The cluster contract (identical shape for kind / eks / gke) ---

output "name" {
  value = aws_eks_cluster.this.name
}

output "host" {
  value = aws_eks_cluster.this.endpoint
}

output "cluster_ca_certificate" {
  value = aws_eks_cluster.this.certificate_authority[0].data
}

output "platform" {
  value = {
    cloud         = "aws"
    storage_class = "gp2"
    base_domain   = var.base_domain
    ingress_values = {
      controller = {
        service = {
          type = "LoadBalancer"
          annotations = {
            "service.beta.kubernetes.io/aws-load-balancer-type"   = "nlb"
            "service.beta.kubernetes.io/aws-load-balancer-scheme" = "internet-facing"
            # "nlb-target-type: ip" would require the AWS Load Balancer Controller; the in-tree
            # controller provisions an instance-target NLB from the two annotations above.
          }
        }
      }
    }
  }
}
