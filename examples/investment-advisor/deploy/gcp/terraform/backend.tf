# Terraform Backend Configuration
# This stores Terraform state in Google Cloud Storage for team collaboration
# and state locking.
#
# FIRST TIME SETUP:
# 1. Create the GCS bucket manually or via gcloud:
#    gcloud storage buckets create gs://investment-advisor-tfstate --location=europe-west1
# 2. Uncomment the backend block below
# 3. Run: terraform init -migrate-state

# terraform {
#   backend "gcs" {
#     bucket  = "investment-advisor-tfstate"
#     prefix  = "terraform/state"
#   }
# }

# For local development, Terraform uses local state by default.
# Uncomment the backend block above for production/team use.