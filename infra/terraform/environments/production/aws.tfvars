# AWS settings for the production stack (placeholders - replace with your landing-zone IDs).
region                  = "eu-west-1"
vpc_id                  = "vpc-00000000000000000"
private_subnet_ids      = ["subnet-00000000000000001", "subnet-00000000000000002", "subnet-00000000000000003"]
cluster_cidrs           = ["10.0.0.0/16"]
secrets_kms_key_arn     = "arn:aws:kms:eu-west-1:000000000000:key/00000000-0000-0000-0000-000000000000"
public_api_cidrs        = ["203.0.113.0/24"] # CI agents only
node_instance_types     = ["m6i.large"]
node_capacity_type      = "ON_DEMAND"
node_min_size           = 3
node_desired_size       = 3
node_max_size           = 6
database_instance_class = "db.m6g.large"
