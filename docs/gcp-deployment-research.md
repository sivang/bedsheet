# GCP Deployment Research - Bedsheet v0.4

*Research conducted: December 2024*
*Status: Planning phase for Debug UI integration*

## Executive Summary

This document captures research on Google's ADK (Agent Development Kit), Agent Starter Pack, and deployment options for Bedsheet agents on GCP Cloud Run. The goal is to determine the best approach for adding a Debug UI to GCP deployments.

---

## Key Findings

### 1. Deployment Architecture Comparison

| Tool | Deployment Method | UI Included | IaC | Production-Ready |
|------|-------------------|-------------|-----|------------------|
| **ADK CLI** (`adk deploy cloud_run`) | Automated container build | Yes (`--with_ui` flag) | No | Prototyping only |
| **Agent Starter Pack (ASP)** | Custom Dockerfile + Terraform | Yes (own frontend) | Yes | Yes |
| **Bedsheet GCP Target** | Custom Dockerfile + Terraform | No (gap) | Yes | Yes |

### 2. What `adk deploy cloud_run --with_ui` Does

The ADK CLI command is a convenience tool that:
1. Packages your agent code
2. Builds a container image automatically
3. Pushes to Artifact Registry
4. Deploys to Cloud Run
5. Optionally includes the ADK Dev UI (`--with_ui` flag)

**Example:**
```bash
adk deploy cloud_run \
  --project=$PROJECT_ID \
  --region=us-central1 \
  --service_name=my-agent \
  --with_ui \
  .
```

**Key insight:** This is meant for quick prototyping. Production deployments (like ASP) use custom Dockerfile + Terraform.

### 3. ADK Dev UI Features

When deployed with `--with_ui`, ADK provides:
- Browser-based chat interface at the Cloud Run service URL
- Session management
- Execution details viewer
- Token streaming toggle

Access: Simply navigate to the Cloud Run service URL in a browser.

### 4. Multi-Agent Container Architecture

**Both ADK and Bedsheet deploy multi-agent systems in ONE container:**

> "Multiple agents are deployed within a single Cloud Run container instance. Each agent folder requires its own `root_agent` definition." - [ADK Docs](https://google.github.io/adk-docs/deploy/cloud-run/)

- `SequentialAgent` orchestrates sub-agents in-process
- Shared `InvocationContext` passes state between agents
- Scaling = more container replicas (horizontal), NOT separate agent containers

### 5. Why Bedsheet Created Custom Dockerfile/Terraform

From `PROJECT_STATUS.md`:

> "**Reuse, don't reinvent** - Designed to integrate with ASP's Terraform modules (deferred)"

Design rationale:
1. **ASP integration was deferred** - plan to offer `terraform_source: "asp"` later
2. **Control over generated code** - Bedsheet generates ADK-compatible code from Bedsheet agents
3. **Ejectability** - users get full control over infrastructure
4. **No Python CDK for GCP** - Terraform is industry standard (unlike AWS which has CDK)

### 6. Agent Starter Pack (ASP) vs ADK CLI

[Agent Starter Pack](https://github.com/GoogleCloudPlatform/agent-starter-pack) is a **separate project** from ADK:

| Aspect | ADK CLI | Agent Starter Pack |
|--------|---------|-------------------|
| Purpose | Quick prototyping | Production deployments |
| Dockerfile | Auto-generated | Custom, in repo |
| Terraform | None | Full IaC |
| CI/CD | None | Cloud Build + GitHub Actions |
| Frontend | ADK Dev UI | Own "interactive playground" |

ASP does NOT use `adk deploy cloud_run` - it uses custom infrastructure.

---

## Local vs GCP Target Independence

| Aspect | Local Target | GCP Target |
|--------|--------------|------------|
| **Runtime** | FastAPI (custom) | ADK (`google.adk.cli api_server`) |
| **UI** | Bedsheet Debug UI (React/Vite) | None (gap to fill) |
| **Dockerfile** | Multi-stage (Node + Python) | Single-stage (Python only) |
| **Agent invocation** | Direct `agent.invoke()` | ADK LlmAgent wrappers |
| **Port** | 8000 (configurable) | 8080 (Cloud Run standard) |

**Important:** These are completely independent code paths. Changes to GCP will NOT affect local.

---

## Options for Adding UI to GCP

### Option A: Use `adk deploy cloud_run --with_ui`
- **Approach:** Replace Terraform/Cloud Build with ADK CLI command
- **Pros:** Simplest, gets ADK Dev UI immediately
- **Cons:** Loses Terraform/CI-CD, not production-ready, less control

### Option B: Hybrid (Recommended for Dev)
- **Approach:** Keep Terraform for production, add `make dev-ui` target using `adk deploy`
- **Pros:** Best of both worlds - production IaC + quick dev testing
- **Cons:** Two deployment paths to document

### Option C: Include ADK UI libs in Dockerfile
- **Approach:** Figure out how ADK packages its UI, include in our Dockerfile
- **Pros:** Single deployment path with UI
- **Cons:** Reverse-engineering ADK internals, maintenance burden

### Option D: Keep as-is
- **Approach:** Document that users can use `adk deploy` separately for UI testing
- **Pros:** No changes needed
- **Cons:** Poor UX, users don't get easy UI access

---

## Recommended Path Forward

**For v0.4:** Add `make dev-ui` target to GCP Makefile that uses `adk deploy cloud_run --with_ui` for quick testing. Keep Terraform for production deployments.

**For v0.5+:** Evaluate ASP Terraform module integration as originally planned.

---

## Implementation Status (v0.4.0rc5)

**COMPLETED** - December 2024

### Changes Made

1. **`bedsheet/deploy/templates/gcp/Makefile.j2`** - Added two new targets:
   - `make dev-ui-local` - Runs ADK Dev UI locally at http://localhost:8000
   - `make dev-ui` - Deploys to Cloud Run with ADK Dev UI (separate `-dev` service)

2. **`docs/deployment-guide.html`** - Added Step C.8 documenting the Dev UI workflow

### Generated Makefile Output

```makefile
# Development with ADK Dev UI
dev-ui-local:
    python -m google.adk.cli web agent

dev-ui:
    python -m google.adk.cli deploy cloud_run \
        --project $(PROJECT) \
        --region $(REGION) \
        --service_name $(SERVICE)-dev \
        --with_ui \
        agent
```

### User Commands

| Command | Purpose | Result |
|---------|---------|--------|
| `make deploy-terraform` | Production deployment | `my-agent` service |
| `make dev-ui-local` | Local testing with UI | localhost:8000 |
| `make dev-ui` | Cloud Run with Dev UI | `my-agent-dev` service |

### What Was NOT Changed

- Dockerfile.j2 - unchanged
- Terraform templates - unchanged
- CloudBuild templates - unchanged
- CI/CD workflows - unchanged
- Local target - completely independent

---

## Source References

### Official Google Documentation
- [ADK - Cloud Run Deployment](https://google.github.io/adk-docs/deploy/cloud-run/)
- [ADK - Multi-Agent Systems](https://google.github.io/adk-docs/agents/multi-agents/)
- [ADK - Deploying Your Agent](https://google.github.io/adk-docs/deploy/)
- [ADK Overview - Google Cloud](https://cloud.google.com/vertex-ai/generative-ai/docs/agent-development-kit/quickstart)

### Agent Starter Pack
- [GitHub Repository](https://github.com/GoogleCloudPlatform/agent-starter-pack)
- [Deployment Guide](https://googlecloudplatform.github.io/agent-starter-pack/guide/deployment.html)
- [Getting Started](https://googlecloudplatform.github.io/agent-starter-pack/guide/getting-started.html)

### Tutorials & Codelabs
- [Deploy, Manage, and Observe ADK Agent on Cloud Run](https://codelabs.developers.google.com/deploy-manage-observe-adk-cloud-run)
- [Build multi-agentic systems using Google ADK](https://cloud.google.com/blog/products/ai-machine-learning/build-multi-agentic-systems-using-google-adk)

---

## Bedsheet Code References

- `bedsheet/deploy/targets/gcp.py` - GCP target generator
- `bedsheet/deploy/templates/gcp/` - Jinja2 templates
- `bedsheet/deploy/config.py` - GCPTargetConfig schema
- `PROJECT_STATUS.md` - Design decisions and rationale

---

*This document is part of Bedsheet v0.4 "Deploy Anywhere" development.*
