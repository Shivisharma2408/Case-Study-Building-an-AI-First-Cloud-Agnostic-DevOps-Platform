# GCP settings for the production stack (placeholders - replace with your project/network).
project_id       = "my-gcp-project"
region           = "europe-west1"
cluster_location = "europe-west1" # regional = HA control plane + nodes in 3 zones
network          = "prod-vpc"
subnetwork       = "prod-gke"
network_id       = "projects/my-gcp-project/global/networks/prod-vpc"
machine_type     = "e2-standard-4"
spot             = false
node_min_count   = 1 # per zone
node_max_count   = 3
database_tier    = "db-custom-2-7680"
