# GCP settings for the staging stack (placeholders - replace with your project/network).
project_id       = "my-gcp-project"
region           = "europe-west1"
cluster_location = "europe-west1-b" # zonal = cheaper
network          = "default"
subnetwork       = "default"
network_id       = "projects/my-gcp-project/global/networks/default"
machine_type     = "e2-standard-2"
spot             = true # cost-sensitive
node_min_count   = 1
node_max_count   = 2
database_tier    = "db-f1-micro"
