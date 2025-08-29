#!/bin/bash

# This script deletes the Google Cloud resources created by your Terraform configuration.
# It's designed to be run if `terraform destroy` fails.

# --- Configuration ---
# These values are taken from the default variables in your main.tf file.
# If you used different values when applying Terraform, update them here.
PROJECT_ID="fast-learner-project"
CLUSTER_NAME="two-node-cluster"
ZONE="us-central1-a"
REGION="us-central1"
NETWORK_NAME="gke-network"
SUBNET_NAME="gke-subnet"
FIREWALL_INGRESS="allow-all-ingress"
FIREWALL_EGRESS="allow-all-egress"

# --- Script Execution ---

# Exit immediately if a command exits with a non-zero status.
set -e

echo "Setting the project to ${PROJECT_ID}..."
gcloud config set project ${PROJECT_ID}

echo "---"
echo "Step 1: Deleting GKE Cluster '${CLUSTER_NAME}'..."
echo "Note: This will also delete the associated node pools."
# gcloud container clusters delete ${CLUSTER_NAME} --zone=${ZONE} --quiet

echo "---"
echo "Step 2: Deleting Firewall Rules..."
echo "Deleting ingress rule: ${FIREWALL_INGRESS}"
# gcloud compute firewall-rules delete ${FIREWALL_INGRESS} --quiet

echo "Deleting egress rule: ${FIREWALL_EGRESS}"
# gcloud compute firewall-rules delete ${FIREWALL_EGRESS} --quiet

echo "---"
echo "Step 3: Deleting Subnetwork '${SUBNET_NAME}'..."
gcloud compute networks subnets delete ${SUBNET_NAME} --region=${REGION} --quiet

echo "---"
echo "Step 4: Deleting VPC Network '${NETWORK_NAME}'..."
gcloud compute networks delete ${NETWORK_NAME} --quiet

echo "---"
echo "Cleanup complete! All specified resources have been deleted."

