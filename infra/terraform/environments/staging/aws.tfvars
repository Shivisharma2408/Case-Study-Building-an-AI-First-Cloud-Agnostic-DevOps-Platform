# AWS settings for the staging stack (placeholders - replace with your landing-zone IDs).
region                  = "eu-west-1"
vpc_id                  = "vpc-00000000000000000"
private_subnet_ids      = ["subnet-00000000000000001", "subnet-00000000000000002"]
cluster_cidrs           = ["10.0.0.0/16"]
secrets_kms_key_arn     = "arn:aws:kms:eu-west-1:000000000000:key/00000000-0000-0000-0000-000000000000"
node_instance_types     = ["t3.medium", "t3a.medium"]
node_capacity_type      = "SPOT" # cost-sensitive
node_min_size           = 1
node_desired_size       = 1
node_max_size           = 2
database_instance_class = "db.t4g.micro"
