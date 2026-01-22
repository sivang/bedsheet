# investment-advisor - GCP Deployment Guide

This guide walks you through deploying your Bedsheet agent to Google Cloud Platform using Cloud Run and Terraform.

## Overview

This deployment will create the following GCP resources:

- **Cloud Run Service**: Serverless container hosting for your agent
- **Vertex AI Access**: For Gemini model inference
- **Service Account**: Dedicated identity with Vertex AI permissions
- **Artifact Registry**: Container image storage
- **IAM Bindings**: Access controls for the service

**Estimated deployment time**: 5-10 minutes
**Estimated monthly cost**: $0-10 (with Cloud Run's generous free tier)

## Prerequisites Checklist

Before you begin, ensure you have:

- [ ] **Google Cloud SDK (gcloud)** - [Install Guide](https://cloud.google.com/sdk/docs/install)
- [ ] **Terraform** >= 1.0.0 - [Install Guide](https://developer.hashicorp.com/terraform/install)
- [ ] **Docker** - [Install Guide](https://docs.docker.com/get-docker/)
- [ ] **GCP Project** with billing enabled - [Create Project](https://console.cloud.google.com/projectcreate)

Verify your installations:

```bash
gcloud --version
terraform --version
docker --version
```

## Quick Start

If you're comfortable with the defaults, deploy in three commands:

```bash
# 1. Authenticate (uses your existing GCP account)
gcloud auth login
gcloud auth application-default login
gcloud config set project bedsheet-e2e-test

# 2. Set up environment and infrastructure
cp .env.example .env
make setup

# 3. Deploy!
make deploy
```

Your agent will be live at the URL shown in the output.

---

## Step-by-Step Deployment

### Step 1: Authenticate with GCP

Set up your GCP credentials:

```bash
# Login to your GCP account
gcloud auth login

# Set up Application Default Credentials (used by ADK)
gcloud auth application-default login

# Set your project
gcloud config set project bedsheet-e2e-test
```

### Step 2: Configure Environment

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` with your project settings:

```bash
GOOGLE_CLOUD_PROJECT=bedsheet-e2e-test
GOOGLE_CLOUD_LOCATION=europe-west1
```

**No API key needed!** The deployment uses your GCP account's Vertex AI access via Application Default Credentials.

### Step 3: Run Preflight Checks

Verify your environment is properly configured:

```bash
make preflight
```

This command checks:
- gcloud authentication status
- Application Default Credentials (ADC)
- Terraform installation
- Docker daemon status
- Environment file exists

**Fix any issues before proceeding.**

### Step 4: Set Up GCP Resources

Initialize the GCP project and enable required APIs:

```bash
make setup
```

This will:
- Enable Cloud Run, Vertex AI, Artifact Registry, Cloud Build APIs
- Initialize Terraform
- Create infrastructure (service account, container registry)

### Step 5: Deploy Your Agent

You have two deployment options:

#### Option A: Quick Deploy (Cloud Build)

For rapid iteration and development:

```bash
make deploy
```

This uses `gcloud builds submit` for a streamlined deployment without state management.

#### Option B: Terraform Deploy (Recommended for Production)

For full Infrastructure as Code with state management:

```bash
make deploy-terraform
```

Or step-by-step:

```bash
make tf-init    # Initialize Terraform
make tf-plan    # Review what will be created
make tf-apply   # Apply changes
```

### Step 6: Verify Deployment

After deployment, you'll see output like:

```
service_url = "https://investment_advisor-xxxxx-ew.a.run.app"
```

Test your agent:

```bash
curl -X POST https://YOUR_SERVICE_URL/invoke \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, agent!"}'
```

---

## Accessing Your Deployed Agent

### Service URL

Your agent is deployed to:

```
https://investment_advisor-[hash]-eu.a.run.app
```

Find the exact URL:

```bash
gcloud run services describe investment_advisor \
  --region europe-west1 \
  --format 'value(status.url)'
```

### Development UI

For interactive testing with ADK's built-in development UI:

```bash
# Local development (no cloud resources needed)
make dev-ui-local
# Open http://localhost:8000

# Cloud-hosted dev UI (separate service)
make dev-ui
# Opens a -dev suffixed service with full UI
```

The Dev UI provides:
- Chat interface for testing conversations
- Execution trace visualization
- State inspector for debugging
- Evaluation tools

---

## Custom Domain Setup (Optional)

To use a custom domain instead of the Cloud Run URL:

### Step 1: Verify Domain Ownership

```bash
gcloud domains verify YOUR_DOMAIN.com
```

### Step 2: Create Domain Mapping

```bash
gcloud run domain-mappings create \
  --service investment_advisor \
  --domain api.YOUR_DOMAIN.com \
  --region europe-west1
```

### Step 3: Configure DNS

Add the DNS records shown in the output to your domain registrar:
- CNAME record pointing to `ghs.googlehosted.com`
- Or A/AAAA records for apex domains

### Step 4: Wait for SSL Certificate

Google automatically provisions an SSL certificate. This can take 15-30 minutes.

Check status:

```bash
gcloud run domain-mappings describe \
  --domain api.YOUR_DOMAIN.com \
  --region europe-west1
```

---

## Monitoring and Logs

### View Logs

```bash
# Stream live logs
make logs

# Or use gcloud directly
gcloud run logs read investment_advisor \
  --region europe-west1 \
  --limit 100

# Tail logs in real-time
gcloud run logs tail investment_advisor \
  --region europe-west1
```

### GCP Console

Access the full monitoring suite at:

- **Cloud Run Dashboard**: [console.cloud.google.com/run](https://console.cloud.google.com/run?project=bedsheet-e2e-test)
- **Logs Explorer**: [console.cloud.google.com/logs](https://console.cloud.google.com/logs?project=bedsheet-e2e-test)
- **Error Reporting**: [console.cloud.google.com/errors](https://console.cloud.google.com/errors?project=bedsheet-e2e-test)

### Key Metrics to Monitor

In the Cloud Run console, watch for:

- **Request latency**: p50 and p99 response times
- **Instance count**: Auto-scaling behavior
- **Memory utilization**: Ensure you're not hitting limits
- **Error rate**: 4xx and 5xx responses
- **Cold start frequency**: First request after scaling from zero

### Setting Up Alerts

Create alerts for production monitoring:

```bash
# Example: Alert when error rate exceeds 1%
gcloud monitoring policies create \
  --notification-channels=YOUR_CHANNEL_ID \
  --display-name="investment-advisor Error Rate" \
  --condition-display-name="High Error Rate" \
  --condition-filter='resource.type="cloud_run_revision" AND metric.type="run.googleapis.com/request_count" AND metric.labels.response_code_class!="2xx"'
```

---

## Troubleshooting

### Common Issues

#### "Permission denied" errors

Ensure your account has the required roles:

```bash
# Check current permissions
gcloud projects get-iam-policy bedsheet-e2e-test \
  --flatten="bindings[].members" \
  --filter="bindings.members:YOUR_EMAIL"

# Grant required roles (run as project owner)
gcloud projects add-iam-policy-binding bedsheet-e2e-test \
  --member="user:YOUR_EMAIL" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding bedsheet-e2e-test \
  --member="user:YOUR_EMAIL" \
  --role="roles/aiplatform.user"
```

#### "API not enabled" errors

Enable the required APIs:

```bash
gcloud services enable \
  run.googleapis.com \
  aiplatform.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  --project=bedsheet-e2e-test
```

#### Container build failures

Check Cloud Build logs:

```bash
gcloud builds list --limit=5
gcloud builds log BUILD_ID
```

Common fixes:
- Ensure Dockerfile syntax is correct
- Check that all dependencies are specified in `pyproject.toml`
- Verify base image is accessible

#### "Vertex AI permission denied" errors

Ensure the service account has Vertex AI access:

```bash
# Grant Vertex AI user role to the service account
gcloud projects add-iam-policy-binding bedsheet-e2e-test \
  --member="serviceAccount:investment_advisor-sa@bedsheet-e2e-test.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"
```

For local development, ensure ADC is configured:

```bash
gcloud auth application-default login
```

#### Cold start latency issues

If cold starts are too slow:

1. **Increase minimum instances** (adds cost):
   ```bash
   gcloud run services update investment_advisor \
     --min-instances=1 \
     --region europe-west1
   ```

2. **Optimize container startup**:
   - Use smaller base images
   - Lazy-load heavy dependencies
   - Reduce initialization logic

#### Memory limit exceeded

Increase memory allocation in `terraform.tfvars`:

```hcl
# terraform.tfvars
cloud_run_memory = "1Gi"  # Or "2Gi" for larger workloads
```

Then redeploy:

```bash
make tf-apply
```

### Getting Help

- **Bedsheet Issues**: [github.com/sivang/bedsheet/issues](https://github.com/sivang/bedsheet/issues)
- **Cloud Run Docs**: [cloud.google.com/run/docs](https://cloud.google.com/run/docs)
- **Google ADK Docs**: [google.github.io/adk-docs](https://google.github.io/adk-docs)

---

## Cleanup

To remove all deployed resources and stop incurring costs:

### Quick Cleanup

```bash
make tf-destroy
```

This will prompt for confirmation before destroying:
- Cloud Run service
- Service account
- Artifact Registry repository
- IAM bindings

### Manual Cleanup

If Terraform state is corrupted or you deployed via Cloud Build:

```bash
# Delete Cloud Run service
gcloud run services delete investment_advisor \
  --region europe-west1 \
  --quiet

# Delete container images from Artifact Registry
gcloud artifacts docker images delete \
  europe-west1-docker.pkg.dev/bedsheet-e2e-test/investment_advisor-repo/investment_advisor \
  --delete-tags \
  --quiet

# Delete Artifact Registry repository
gcloud artifacts repositories delete investment_advisor-repo \
  --location=europe-west1 \
  --quiet

# Delete service account
gcloud iam service-accounts delete investment_advisor-sa@bedsheet-e2e-test.iam.gserviceaccount.com \
  --quiet
```

### Verify Cleanup

Confirm no resources remain:

```bash
gcloud run services list --region europe-west1
gcloud artifacts repositories list --location=europe-west1
gcloud iam service-accounts list
```

---

## Next Steps

Now that your agent is deployed:

1. **Add Authentication**: Set `allow_unauthenticated = false` in `terraform.tfvars` and configure IAM
2. **Set Up CI/CD**: Use the included `.github/workflows/` templates
3. **Add Monitoring**: Configure Cloud Monitoring dashboards and alerts
4. **Scale Up**: Adjust min/max instances and memory as needed
5. **Add Custom Domain**: Follow the custom domain setup above

For more information, see the [Bedsheet Documentation](https://sivang.github.io/bedsheet/).