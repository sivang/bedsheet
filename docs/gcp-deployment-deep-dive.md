# GCP Deployment Deep Dive

> **Bedsheet v0.4.x** - Comprehensive guide to deploying AI agents on Google Cloud Platform

This document captures everything learned from building and debugging the GCP deployment target, including architecture, authentication patterns, troubleshooting, and the template system that makes deployment frictionless.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Authentication Deep Dive](#authentication-deep-dive)
3. [The ADK Integration](#the-adk-integration)
4. [Template System](#template-system)
5. [Deployment Flow](#deployment-flow)
6. [Troubleshooting Guide](#troubleshooting-guide)
7. [The Great Debugging of January 2026](#the-great-debugging-of-january-2026)
8. [Future Considerations](#future-considerations)

---

## Architecture Overview

### High-Level System Architecture

```mermaid
graph TB
    subgraph "Developer Machine"
        DEV[Developer]
        CLI[bedsheet CLI]
        TEMPLATES[Jinja2 Templates]
        AGENT_CODE[Agent Python Code]
    end

    subgraph "Google Cloud Platform"
        subgraph "Cloud Build"
            CB[Cloud Build]
            AR[Artifact Registry]
        end

        subgraph "Cloud Run"
            CR[Cloud Run Service]
            ADK[ADK Web Server]
            AGENT[Bedsheet Agent]
        end

        subgraph "Vertex AI"
            GEMINI[Gemini 3 Flash]
            GLOBAL[Global Endpoint]
        end

        subgraph "IAM & Auth"
            SA[Service Account]
            IAM[IAM Roles]
        end
    end

    DEV -->|bedsheet generate| CLI
    CLI -->|renders| TEMPLATES
    TEMPLATES -->|creates| DEPLOY[deploy/gcp/]

    DEPLOY -->|make deploy| CB
    CB -->|builds| AR
    AR -->|deploys to| CR

    CR -->|runs| ADK
    ADK -->|hosts| AGENT
    AGENT -->|calls| GEMINI

    SA -->|authenticates| CR
    IAM -->|authorizes| GEMINI
```

### Component Responsibilities

| Component | Responsibility |
|-----------|---------------|
| **bedsheet CLI** | Generates deployment artifacts from templates |
| **Jinja2 Templates** | Define infrastructure-as-code and runtime configuration |
| **Cloud Build** | CI/CD pipeline for building and deploying |
| **Artifact Registry** | Docker image storage |
| **Cloud Run** | Serverless container hosting |
| **ADK Web Server** | Google's Agent Development Kit runtime |
| **Vertex AI** | Gemini model API (global endpoint for Gemini 3) |
| **Service Account** | Workload identity for Cloud Run |

### Multi-Agent Architecture

```mermaid
graph LR
    subgraph "Cloud Run Container"
        subgraph "ADK Runtime"
            ROOT[InvestmentAdvisor<br/>Supervisor Agent]

            subgraph "Collaborators"
                MA[MarketAnalyst]
                NR[NewsResearcher]
                RA[RiskAnalyst]
            end
        end
    end

    USER[User] -->|HTTP/SSE| ROOT
    ROOT -->|delegates| MA
    ROOT -->|delegates| NR
    ROOT -->|delegates| RA

    MA -->|Vertex AI| GEMINI[Gemini 3 Flash]
    NR -->|Vertex AI| GEMINI
    RA -->|Vertex AI| GEMINI

    MA -->|tools| TOOLS1[get_stock_data<br/>get_technical_analysis]
    NR -->|tools| TOOLS2[search_news<br/>analyze_sentiment]
    RA -->|tools| TOOLS3[analyze_volatility<br/>get_position_recommendation]
```

---

## Authentication Deep Dive

### The Authentication Stack

Understanding GCP authentication is **critical** for debugging. There are multiple layers:

```mermaid
graph TB
    subgraph "Authentication Sources (Priority Order)"
        ENV["1. GOOGLE_APPLICATION_CREDENTIALS<br/>(Environment Variable)"]
        ADC["2. Application Default Credentials<br/>(~/.config/gcloud/application_default_credentials.json)"]
        META["3. Metadata Server<br/>(GCE/Cloud Run Service Account)"]
    end

    subgraph "What Uses Each"
        ENV -->|"Python SDK<br/>google-genai"| SDK1[SDK picks this FIRST]
        ADC -->|"Fallback when<br/>ENV not set"| SDK2[SDK fallback]
        META -->|"Only on GCP<br/>infrastructure"| SDK3[Production runtime]
    end

    subgraph "Common Gotcha"
        WRONG[ENV points to<br/>Project A's SA]
        TARGET[Trying to access<br/>Project B's resources]
        WRONG --> FAIL[403 PERMISSION_DENIED]
        TARGET --> FAIL
    end
```

### Credential Priority Deep Dive

```python
# How google-auth resolves credentials (simplified)
def get_credentials():
    # 1. GOOGLE_APPLICATION_CREDENTIALS takes highest priority
    if os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
        return service_account.Credentials.from_service_account_file(
            os.environ['GOOGLE_APPLICATION_CREDENTIALS']
        )

    # 2. Application Default Credentials
    if os.path.exists('~/.config/gcloud/application_default_credentials.json'):
        return load_adc_credentials()

    # 3. Metadata server (GCE, Cloud Run, GKE, etc.)
    if running_on_gcp():
        return compute_engine.Credentials()

    raise NoCredentialsError()
```

### The January 2026 Bug Explained

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant SDK as google-genai SDK
    participant ENV as Environment
    participant ADC as ADC File
    participant OtherProj as other-project-id
    participant Bedsheet as bedsheet-e2e-test
    participant Gemini as Vertex AI Gemini

    Note over Dev,Gemini: The Bug Scenario

    Dev->>SDK: genai.Client(project='bedsheet-e2e-test')
    SDK->>ENV: Check GOOGLE_APPLICATION_CREDENTIALS
    ENV-->>SDK: /path/to/other-project-service-account.json
    SDK->>SDK: Load other-project SA credentials

    Note over SDK: SDK now has other-project SA,<br/>but targeting bedsheet project!

    SDK->>Gemini: Request to bedsheet-e2e-test/gemini-3-flash
    Gemini->>Gemini: Check: Does other-project SA have<br/>access to bedsheet project?
    Gemini-->>SDK: 403 PERMISSION_DENIED

    Note over Dev,Gemini: The Fix

    Dev->>ENV: unset GOOGLE_APPLICATION_CREDENTIALS
    Dev->>SDK: genai.Client(project='bedsheet-e2e-test')
    SDK->>ENV: Check GOOGLE_APPLICATION_CREDENTIALS
    ENV-->>SDK: Not set
    SDK->>ADC: Load ADC credentials
    ADC-->>SDK: User credentials with bedsheet quota
    SDK->>Gemini: Request to bedsheet-e2e-test/gemini-3-flash
    Gemini-->>SDK: 200 OK + Response
```

### Authentication Checklist

Before deploying or debugging, verify:

```bash
# 1. Check if GOOGLE_APPLICATION_CREDENTIALS is set
echo $GOOGLE_APPLICATION_CREDENTIALS
# If set to wrong project's SA, unset it:
unset GOOGLE_APPLICATION_CREDENTIALS

# 2. Check current gcloud auth
gcloud auth list

# 3. Check ADC configuration
cat ~/.config/gcloud/application_default_credentials.json | jq '.quota_project_id'

# 4. Verify ADC works for your project
gcloud auth application-default print-access-token

# 5. Test direct API access
curl -s -X POST \
  "https://aiplatform.googleapis.com/v1/projects/YOUR_PROJECT/locations/global/publishers/google/models/gemini-3-flash-preview:generateContent" \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -d '{"contents":[{"role":"user","parts":[{"text":"Hi"}]}]}'
```

---

## The ADK Integration

### What is ADK?

**Agent Development Kit (ADK)** is Google's framework for building AI agents. Bedsheet generates ADK-compatible agents for GCP deployment.

### ADK Server Modes

```mermaid
graph LR
    subgraph "api_server mode"
        API[adk api_server]
        API --> EP1["/run - Batch response"]
        API --> EP2["/run_sse - Streaming"]
        API --> EP3["/apps/*/sessions/*"]
    end

    subgraph "web mode"
        WEB[adk web]
        WEB --> EP4["/run, /run_sse, /apps/*"]
        WEB --> EP5["/dev-ui/ - Interactive UI"]
        WEB --> EP6["/debug/trace/*"]
    end

    style WEB fill:#90EE90
    style EP5 fill:#90EE90
```

**Key Decision:** We use `web` mode in production because:
1. Includes all API endpoints
2. Provides Dev UI for debugging deployed agents
3. Enables trace visualization
4. No performance penalty

### ADK Directory Structure

```
deploy/gcp/
├── agent/                    # ADK agent directory
│   ├── __init__.py          # Exports root_agent
│   ├── agent.py             # Agent definition (generated from Bedsheet)
│   └── tools.py             # Tool implementations
├── Dockerfile               # Container definition
├── pyproject.toml           # Dependencies
├── Makefile                 # Deployment commands
├── cloudbuild.yaml          # CI/CD pipeline
└── terraform/               # Infrastructure as code
    ├── main.tf
    ├── variables.tf
    └── outputs.tf
```

### The root_agent Pattern

ADK discovers agents by looking for `root_agent` in the agent module:

```python
# agent/__init__.py
from .agent import root_agent

# agent/agent.py
from google.adk.agents import LlmAgent

root_agent = LlmAgent(
    name="InvestmentAdvisor",
    model="gemini-3-flash-preview",
    instruction="You are an investment advisor...",
    sub_agents=[market_analyst, news_researcher, risk_analyst]
)
```

---

## Template System

### How Bedsheet Templates Work

```mermaid
graph TB
    subgraph "Input"
        YAML[bedsheet.yaml]
        AGENT[agents.py]
    end

    subgraph "bedsheet generate --target gcp"
        PARSE[Parse Config]
        INTRO[Introspect Agents]
        RENDER[Render Templates]
    end

    subgraph "Templates (bedsheet/deploy/templates/gcp/)"
        T1[Dockerfile.j2]
        T2[Makefile.j2]
        T3[cloudbuild.yaml.j2]
        T4[main.tf.j2]
        T5[agent.py.j2]
        T6["__init__.py.j2"]
    end

    subgraph "Output (deploy/gcp/)"
        O1[Dockerfile]
        O2[Makefile]
        O3[cloudbuild.yaml]
        O4[terraform/main.tf]
        O5[agent/agent.py]
        O6["agent/__init__.py"]
    end

    YAML --> PARSE
    AGENT --> INTRO
    PARSE --> RENDER
    INTRO --> RENDER

    T1 --> RENDER
    T2 --> RENDER
    T3 --> RENDER
    T4 --> RENDER
    T5 --> RENDER
    T6 --> RENDER

    RENDER --> O1
    RENDER --> O2
    RENDER --> O3
    RENDER --> O4
    RENDER --> O5
    RENDER --> O6
```

### Key Template: Dockerfile.j2

```dockerfile
# {{ config.name }} - Cloud Run Container
# Generated by: bedsheet generate --target gcp

FROM python:3.11-slim

# Install uv (fast Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies from pyproject.toml
COPY pyproject.toml .
RUN uv pip install --system -r pyproject.toml

# Copy agent code
COPY agent/ ./agent/

# Cloud Run expects PORT env var
ENV PORT=8080

# ADK serves the agent with Dev UI
# Using "web" mode to include the interactive Dev UI at root path
CMD ["python", "-m", "google.adk.cli", "web", "--host", "0.0.0.0", "--port", "8080", "."]
```

**Why `web` mode?**
- `api_server`: API only, no UI
- `web`: API + Dev UI at `/dev-ui/`

### Key Template: cloudbuild.yaml.j2

```yaml
steps:
  # Step 1: Enable required APIs
  - name: 'gcr.io/cloud-builders/gcloud'
    entrypoint: 'bash'
    args:
      - '-c'
      - |
        gcloud services enable \
          run.googleapis.com \
          artifactregistry.googleapis.com \
          cloudbuild.googleapis.com \
          aiplatform.googleapis.com \
          --project=$PROJECT_ID

  # Step 2: Create Artifact Registry (if not exists)
  - name: 'gcr.io/cloud-builders/gcloud'
    entrypoint: 'bash'
    args:
      - '-c'
      - |
        gcloud artifacts repositories describe {{ config.name }}-repo \
          --location={{ gcp.region }} \
          --project=$PROJECT_ID 2>/dev/null || \
        gcloud artifacts repositories create {{ config.name }}-repo \
          --repository-format=docker \
          --location={{ gcp.region }} \
          --project=$PROJECT_ID

  # Step 3: Build container
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', '{{ gcp.region }}-docker.pkg.dev/$PROJECT_ID/{{ config.name }}-repo/{{ config.name }}:$BUILD_ID', '.']

  # Step 4: Push to Artifact Registry
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', '{{ gcp.region }}-docker.pkg.dev/$PROJECT_ID/{{ config.name }}-repo/{{ config.name }}:$BUILD_ID']

  # Step 5: Deploy to Cloud Run
  - name: 'gcr.io/cloud-builders/gcloud'
    args:
      - 'run'
      - 'deploy'
      - '{{ config.name }}'
      - '--image={{ gcp.region }}-docker.pkg.dev/$PROJECT_ID/{{ config.name }}-repo/{{ config.name }}:$BUILD_ID'
      - '--region={{ gcp.region }}'
      - '--platform=managed'
      - '--memory={{ gcp.cloud_run_memory }}'
      - '--allow-unauthenticated'  # Or use IAM for auth
      - '--set-env-vars=GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=global'

images:
  - '{{ gcp.region }}-docker.pkg.dev/$PROJECT_ID/{{ config.name }}-repo/{{ config.name }}:$BUILD_ID'
```

### Template Variables

| Variable | Source | Example |
|----------|--------|---------|
| `config.name` | bedsheet.yaml | `investment-advisor` |
| `config.agents` | bedsheet.yaml + introspection | Agent metadata |
| `gcp.project` | bedsheet.yaml targets.gcp | `bedsheet-e2e-test` |
| `gcp.region` | bedsheet.yaml targets.gcp | `europe-west1` |
| `gcp.model` | bedsheet.yaml targets.gcp | `gemini-3-flash-preview` |
| `gcp.cloud_run_memory` | bedsheet.yaml targets.gcp | `1Gi` |

---

## Deployment Flow

### Complete Deployment Sequence

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant CLI as bedsheet CLI
    participant Make as Makefile
    participant CB as Cloud Build
    participant AR as Artifact Registry
    participant CR as Cloud Run
    participant VA as Vertex AI

    Note over Dev,VA: Phase 1: Generate
    Dev->>CLI: bedsheet generate --target gcp
    CLI->>CLI: Load bedsheet.yaml
    CLI->>CLI: Introspect agent code
    CLI->>CLI: Render Jinja2 templates
    CLI-->>Dev: deploy/gcp/ created

    Note over Dev,VA: Phase 2: Setup (one-time)
    Dev->>Make: make setup
    Make->>Make: Check tools (gcloud, terraform)
    Make->>Make: Authenticate (gcloud auth)
    Make->>Make: Set project
    Make-->>Dev: Ready to deploy

    Note over Dev,VA: Phase 3: Deploy
    Dev->>Make: make deploy
    Make->>CB: gcloud builds submit
    CB->>CB: Enable APIs
    CB->>AR: Create repo (if needed)
    CB->>CB: docker build
    CB->>AR: docker push
    CB->>CR: gcloud run deploy
    CR->>CR: Pull image
    CR->>CR: Start container
    CR-->>Dev: Service URL

    Note over Dev,VA: Phase 4: Runtime
    Dev->>CR: HTTP request to /run
    CR->>VA: Gemini API call
    VA-->>CR: Model response
    CR-->>Dev: Agent response
```

### Make Targets

```makefile
# Quick reference for all make targets

make help      # Show all available commands
make setup     # One-time setup (auth, project, APIs)
make deploy    # Deploy to Cloud Run via Cloud Build
make dev       # Run locally with ADK Dev UI
make test      # Test agent via CLI
make logs      # Stream Cloud Run logs
make status    # Show deployment status
make url       # Get service URL
make destroy   # Remove all resources
```

---

## Troubleshooting Guide

### Common Issues and Solutions

#### 1. 403 PERMISSION_DENIED on Vertex AI

```
Error: Permission 'aiplatform.endpoints.predict' denied on resource
```

**Diagnosis Flow:**

```mermaid
graph TD
    A[403 PERMISSION_DENIED] --> B{Is GOOGLE_APPLICATION_CREDENTIALS set?}
    B -->|Yes| C{Does SA have access to target project?}
    B -->|No| D{Is ADC configured?}

    C -->|No| E[Unset env var or use correct SA]
    C -->|Yes| F{Is aiplatform.googleapis.com enabled?}

    D -->|No| G[Run: gcloud auth application-default login]
    D -->|Yes| H{Is quota project correct?}

    F -->|No| I[Enable API: gcloud services enable aiplatform.googleapis.com]
    F -->|Yes| J{Does user have Vertex AI User role?}

    H -->|No| K[Run: gcloud auth application-default set-quota-project PROJECT]
    H -->|Yes| J

    J -->|No| L[Grant role: roles/aiplatform.user]
    J -->|Yes| M[Check model availability in region]

    E --> N[Fixed!]
    G --> N
    I --> N
    K --> N
    L --> N
```

**Quick Fix:**

```bash
# Nuclear option: reset all auth
unset GOOGLE_APPLICATION_CREDENTIALS
gcloud auth application-default login --scopes="https://www.googleapis.com/auth/cloud-platform"
gcloud auth application-default set-quota-project YOUR_PROJECT
```

#### 2. Gemini 3 Model Not Found

```
Error: Model gemini-3-flash-preview not found
```

**Solutions:**
1. Use global endpoint: `GOOGLE_CLOUD_LOCATION=global`
2. Check model name is exactly `gemini-3-flash-preview`
3. Verify SDK version >= 1.51.0: `pip show google-genai`

#### 3. Cloud Build Fails

```
Error: Build failed
```

**Check:**
```bash
# View build logs
gcloud builds log BUILD_ID --project=YOUR_PROJECT

# Common issues:
# - APIs not enabled (fixed by cloudbuild.yaml step 1)
# - Insufficient permissions (need Cloud Build Editor role)
# - Dockerfile syntax error
```

#### 4. Cloud Run 503 Service Unavailable

```
Error: 503 Service Unavailable
```

**Check:**
```bash
# View container logs
gcloud run services logs read SERVICE_NAME --region=REGION

# Common issues:
# - Container crashing (check startup logs)
# - Memory limit too low (increase cloud_run_memory)
# - Missing environment variables
```

#### 5. ADK Dev UI Not Loading

```
GET /dev-ui/ returns 404
```

**Solution:** Dockerfile must use `web` mode, not `api_server`:

```dockerfile
# Wrong
CMD ["python", "-m", "google.adk.cli", "api_server", ...]

# Correct
CMD ["python", "-m", "google.adk.cli", "web", ...]
```

### Debug Commands Cheat Sheet

```bash
# === Authentication Debugging ===
echo $GOOGLE_APPLICATION_CREDENTIALS     # Check if set
gcloud auth list                          # Current accounts
gcloud config get-value project           # Current project
gcloud auth application-default print-access-token  # Test ADC

# === API Testing ===
# Direct curl to Vertex AI (bypasses SDK)
curl -s -X POST \
  "https://aiplatform.googleapis.com/v1/projects/PROJECT/locations/global/publishers/google/models/gemini-3-flash-preview:generateContent" \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -d '{"contents":[{"role":"user","parts":[{"text":"Hi"}]}]}'

# === Cloud Run Debugging ===
gcloud run services describe SERVICE --region=REGION
gcloud run services logs read SERVICE --region=REGION --limit=50

# === Local Testing ===
cd deploy/gcp && make dev  # Start local ADK server
curl http://localhost:8000/list-apps  # Test local API
```

---

## The Great Debugging of January 2026

### The Problem

Investment Advisor agent deployed successfully to Cloud Run but returned 403 PERMISSION_DENIED when calling Gemini 3 Flash.

### The Mystery

| Test | Result |
|------|--------|
| `curl` with `gcloud auth print-access-token` | ✅ Worked |
| Python SDK with project `other-project-id` | ✅ Worked |
| Python SDK with project `bedsheet-e2e-test` | ❌ 403 Error |
| Both projects had same APIs enabled | ✅ Verified |
| Both projects had same billing | ✅ Verified |

### The Investigation

```mermaid
graph TB
    A[Start: 403 Error] --> B[Check APIs]
    B --> C[Both projects have aiplatform.googleapis.com ✓]

    C --> D[Check IAM]
    D --> E[User has Owner role ✓]

    E --> F[Try curl directly]
    F --> G[curl works! ✓]

    G --> H[SDK uses different auth?]
    H --> I[Check google.auth.default]

    I --> J[ERROR: invalid_scope]
    J --> K[SDK picking up service account!]

    K --> L[Check env vars]
    L --> M[GOOGLE_APPLICATION_CREDENTIALS set!]

    M --> N[Points to other-project SA]
    N --> O[SDK uses other-project SA for bedsheet project]
    O --> P[403 - other-project SA has no access to bedsheet]

    P --> Q[unset GOOGLE_APPLICATION_CREDENTIALS]
    Q --> R[SDK now uses ADC]
    R --> S[✅ FIXED!]

    style A fill:#ff6b6b
    style S fill:#51cf66
```

### The Root Cause

```bash
# This was set in the developer's shell:
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/other-project-service-account.json
```

This service account had permissions for `other-project-id` but NOT for `bedsheet-e2e-test`. The Python SDK **prioritizes** this environment variable over ADC.

### The Fix

```bash
unset GOOGLE_APPLICATION_CREDENTIALS
```

Or ensure it points to the correct project's service account.

### Lessons Learned

1. **Check environment variables first** when debugging auth issues
2. **Credential priority matters**: ENV > ADC > Metadata
3. **curl working but SDK failing** = different auth sources
4. **Trust your instincts**: "It works on another project" means the API works
5. **Multiple GCP projects** require careful credential management

---

## Future Considerations

### Potential Improvements

#### 1. Credential Validation in Templates

Add a pre-flight check in the Makefile:

```makefile
_validate_credentials:
    @echo "Checking credentials..."
    @if [ -n "$$GOOGLE_APPLICATION_CREDENTIALS" ]; then \
        echo "WARNING: GOOGLE_APPLICATION_CREDENTIALS is set to: $$GOOGLE_APPLICATION_CREDENTIALS"; \
        echo "This may cause authentication issues if it points to a different project."; \
        echo "Consider running: unset GOOGLE_APPLICATION_CREDENTIALS"; \
    fi
```

#### 2. Project-Specific Service Account

Generate a service account for each deployment:

```terraform
resource "google_service_account" "agent_sa" {
  account_id   = "${var.service_name}-sa"
  display_name = "Service Account for ${var.service_name}"
  project      = var.project_id
}

resource "google_project_iam_member" "vertex_ai_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.agent_sa.email}"
}
```

#### 3. Multi-Region Deployment

Support deploying to multiple regions for redundancy:

```yaml
# bedsheet.yaml
targets:
  gcp:
    project: my-project
    regions:
      - us-central1
      - europe-west1
      - asia-northeast1
```

#### 4. Custom Domain Support

Add Cloud Load Balancer with custom domain:

```terraform
resource "google_compute_global_address" "default" {
  name = "${var.service_name}-ip"
}

resource "google_compute_managed_ssl_certificate" "default" {
  name = "${var.service_name}-cert"
  managed {
    domains = [var.custom_domain]
  }
}
```

### Roadmap Integration

| Version | Feature | Status |
|---------|---------|--------|
| v0.4.2 | GCP E2E Testing Complete | ✅ Done |
| v0.4.2 | ADK Dev UI in Cloud Run | ✅ Done |
| v0.5.0 | Knowledge Bases / RAG | Planned |
| v0.6.0 | Guardrails / Safety | Planned |
| v0.7.0 | Agent Engine (managed) | Planned |

---

## Quick Reference Card

### Deploy a New Agent to GCP

```bash
# 1. Create agent
bedsheet init my-agent
cd my-agent

# 2. Configure (edit bedsheet.yaml)
cat > bedsheet.yaml << 'EOF'
version: '1.0'
name: my-agent
agents:
  - name: MyAgent
    module: agents
    class_name: MyAgent
target: gcp
targets:
  gcp:
    project: YOUR_PROJECT_ID
    region: us-central1
    model: gemini-3-flash-preview
EOF

# 3. Generate deployment artifacts
bedsheet generate --target gcp

# 4. Deploy
cd deploy/gcp
make setup   # One-time
make deploy  # Deploy to Cloud Run

# 5. Test
make url     # Get service URL
curl -X POST $(make url)/run -H "Content-Type: application/json" \
  -d '{"app_name":"agent","user_id":"test","session_id":"1","new_message":{"role":"user","parts":[{"text":"Hello"}]}}'
```

### Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `GOOGLE_CLOUD_PROJECT` | Target GCP project | Yes |
| `GOOGLE_CLOUD_LOCATION` | Model location (`global` for Gemini 3) | Yes |
| `GOOGLE_GENAI_USE_VERTEXAI` | Use Vertex AI (not AI Studio) | Yes (`True`) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Service account key path | No (use ADC) |

### Useful Links

- [Bedsheet GitHub](https://github.com/sivang/bedsheet)
- [ADK Documentation](https://google.github.io/adk-docs/)
- [Vertex AI Gemini](https://cloud.google.com/vertex-ai/generative-ai/docs/models/gemini)
- [Cloud Run Documentation](https://cloud.google.com/run/docs)

---

*Document created: January 22, 2026*
*Last updated: January 22, 2026*
*Author: Bedsheet Team*

**Live Long and Prosper! 🖖**
