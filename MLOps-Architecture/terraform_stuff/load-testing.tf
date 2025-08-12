# load-testing.tf

# -----------------------------------------------------------------------------
# CREATE LOAD TESTING INSTANCE
# -----------------------------------------------------------------------------
resource "google_compute_instance" "load_testing_instance" {
  name         = "load-testing-instance"
  machine_type = "e2-standard-8"
  zone         = "us-central1-a"

  boot_disk {
    initialize_params {
      image = "ubuntu-os-pro-cloud/ubuntu-pro-2004-focal-v20250729"
      type  = "pd-standard"
      size  = 30
    }
  }

  network_interface {
    network    = google_compute_network.vpc_network.id
    subnetwork = google_compute_subnetwork.vpc_subnetwork.id
    
    access_config {
      # Ephemeral public IP
    }
  }

  metadata = {
    enable-oslogin = "FALSE"
  }

  service_account {
    email = google_service_account.load_testing_sa.email
    scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]
  }

  tags = ["load-testing", "gke-node"]

  allow_stopping_for_update = true
}

# -----------------------------------------------------------------------------
# CREATE SERVICE ACCOUNT FOR LOAD TESTING INSTANCE
# -----------------------------------------------------------------------------
resource "google_service_account" "load_testing_sa" {
  account_id   = "load-testing-sa"
  display_name = "Load Testing Service Account"
  description  = "Service account for load testing instance"
}

resource "google_project_iam_member" "load_testing_sa_roles" {
  for_each = toset([
    "roles/compute.instanceAdmin",
    "roles/container.developer",
    "roles/monitoring.metricWriter",
    "roles/logging.logWriter"
  ])
  
  project = "fast-learner-project"
  role    = each.value
  member  = "serviceAccount:${google_service_account.load_testing_sa.email}"
}

# -----------------------------------------------------------------------------
# FIREWALL RULES FOR LOAD TESTING INSTANCE
# -----------------------------------------------------------------------------
resource "google_compute_firewall" "load_testing_ingress" {
  name    = "load-testing-allow-all-ingress"
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

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["load-testing"]
}

resource "google_compute_firewall" "load_testing_egress" {
  name      = "load-testing-allow-all-egress"
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

  destination_ranges = ["0.0.0.0/0"]
  target_tags        = ["load-testing"]
}

# -----------------------------------------------------------------------------
# OUTPUTS
# -----------------------------------------------------------------------------
output "load_testing_instance_name" {
  description = "The name of the load testing instance"
  value       = google_compute_instance.load_testing_instance.name
}

output "load_testing_instance_external_ip" {
  description = "The external IP address of the load testing instance"
  value       = google_compute_instance.load_testing_instance.network_interface[0].access_config[0].nat_ip
}

output "load_testing_instance_internal_ip" {
  description = "The internal IP address of the load testing instance"
  value       = google_compute_instance.load_testing_instance.network_interface[0].network_ip
}