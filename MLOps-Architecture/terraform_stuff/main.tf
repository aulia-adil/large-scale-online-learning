# main.tf

# -----------------------------------------------------------------------------
# CONFIGURE THE GOOGLE CLOUD PROVIDER
# -----------------------------------------------------------------------------
terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  # Replace with your project ID and desired region
  project = "fast-learner-project"
  region  = var.region
}

# -----------------------------------------------------------------------------
# DEFINE VARIABLES
# -----------------------------------------------------------------------------
variable "gke_cluster_name" {
  description = "The name for the GKE cluster."
  type        = string
  default     = "two-node-cluster"
}

variable "gke_network_name" {
  description = "The name of the VPC network for the GKE cluster."
  type        = string
  default     = "gke-network"
}

variable "gke_subnetwork_name" {
  description = "The name of the subnetwork for the GKE cluster."
  type        = string
  default     = "gke-subnet"
}

variable "region" {
  description = "The region where resources will be created."
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "The zone for zonal resources."
  type        = string
  default     = "us-central1-a"
}

# -----------------------------------------------------------------------------
# CREATE VPC NETWORK AND SUBNETWORK
# -----------------------------------------------------------------------------
resource "google_compute_network" "vpc_network" {
  name                    = var.gke_network_name
  auto_create_subnetworks = false # We will create a custom subnet
}

resource "google_compute_subnetwork" "vpc_subnetwork" {
  name          = var.gke_subnetwork_name
  ip_cidr_range = "10.10.0.0/24"
  region        = var.region
  network       = google_compute_network.vpc_network.id
}

# -----------------------------------------------------------------------------
# CREATE THE GKE CLUSTER (PRIMARY CONTROL PLANE)
# -----------------------------------------------------------------------------
resource "google_container_cluster" "primary_cluster" {
  name     = var.gke_cluster_name
  location = var.zone

  # We will create node pools separately, so we remove the default one.
  remove_default_node_pool = true
  initial_node_count       = 1

  network    = google_compute_network.vpc_network.id
  subnetwork = google_compute_subnetwork.vpc_subnetwork.id

  deletion_protection = false

  # Make cluster completely open for experiments
  master_authorized_networks_config {
    cidr_blocks {
      cidr_block   = "0.0.0.0/0"
      display_name = "Allow all"
    }
  }

  # Enable public endpoint
  private_cluster_config {
    enable_private_nodes    = false
    enable_private_endpoint = false
  }

  # Disable network policy for maximum openness
  network_policy {
    enabled = false
  }

  # Allow legacy authorization for maximum compatibility
  enable_legacy_abac = true
}

# -----------------------------------------------------------------------------
# CREATE THE FIRST NODE POOL
# -----------------------------------------------------------------------------
resource "google_container_node_pool" "node_pool_1" {
  name       = "node-pool-1"
  location   = var.zone
  cluster    = google_container_cluster.primary_cluster.name
  node_count = 2

  node_config {
    # Specify the machine type for this node pool
    machine_type = "e2-standard-8" # upgraded machine type
    disk_type    = "pd-standard"   # use standard disk instead of SSD
    disk_size_gb = 20               # smaller disk size
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]
    tags = ["gke-node", "pool-1"]
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }
}

# -----------------------------------------------------------------------------
# CREATE FIREWALL RULES (COMPLETELY OPEN FOR EXPERIMENTS)
# -----------------------------------------------------------------------------
resource "google_compute_firewall" "allow_all_ingress" {
  name    = "allow-all-ingress"
  network = google_compute_network.vpc_network.name

  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "udp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "icmp"
  }

  source_ranges = ["0.0.0.0/0"] # Allow from anywhere
  target_tags   = ["gke-node"]
}

resource "google_compute_firewall" "allow_all_egress" {
  name      = "allow-all-egress"
  network   = google_compute_network.vpc_network.name
  direction = "EGRESS"

  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "udp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "icmp"
  }

  destination_ranges = ["0.0.0.0/0"] # Allow to anywhere
  target_tags        = ["gke-node"]
}

# -----------------------------------------------------------------------------
# OUTPUTS
# -----------------------------------------------------------------------------
output "cluster_name" {
  description = "The name of the created GKE cluster."
  value       = google_container_cluster.primary_cluster.name
}

output "cluster_endpoint" {
  description = "The endpoint of the GKE cluster master."
  value       = google_container_cluster.primary_cluster.endpoint
  sensitive   = true
}

output "cluster_ca_certificate" {
  description = "The cluster's root certificate."
  value       = google_container_cluster.primary_cluster.master_auth[0].cluster_ca_certificate
  sensitive   = true
}
