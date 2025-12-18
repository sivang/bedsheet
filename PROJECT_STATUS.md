# Bedsheet Agents - Project Status

## Current Version: v0.4.0rc4 🧪 Testing on PyPI

**Last Session:** 2025-12-18 (Evening)

### Release Status

| Version | Status | Branch |
|---------|--------|--------|
| v0.3.0 | ✅ Released on PyPI | main |
| v0.4.0rc4 | 🧪 Testing on PyPI | development/v0.4-deploy-anywhere |

### Release Artifacts

| Artifact | Status |
|----------|--------|
| Source Code | ✅ Complete |
| Test Suite | ✅ 179 tests passing |
| README.md | ✅ Comprehensive with examples |
| CHANGELOG.md | ✅ v0.1.0, v0.2.0, and v0.3.0 documented |
| CONTRIBUTING.md | ✅ Contributor guidelines |
| LICENSE | ✅ Apache 2.0 (Sivan Grünberg, Vitakka Consulting) |
| CI/CD | ✅ GitHub Actions (test, lint, typecheck) |
| Documentation | ✅ User Guide + Technical Guide + Multi-agent Guide |
| Examples | ✅ Investment advisor demo |
| Demo | ✅ `python -m bedsheet` (requires API key, uses Claude Sonnet 4.5) |
| pyproject.toml | ✅ PyPI ready |

---

## Session Summary (2025-12-18 Evening)

### What Was Done

1. **AWS Terraform @action Translation Fix - COMPLETE!**
   - Fixed critical bug: delegate action was being translated to Lambda/OpenAPI for supervisors
   - AWS Bedrock has NATIVE collaboration via `aws_bedrockagent_agent_collaborator`
   - Delegate @action should only exist for LOCAL execution, not AWS deployment

2. **Delegate Action Filtering**
   - Modified `aws.py` and `aws_terraform.py` to filter delegate BEFORE creating template context
   - For supervisors with collaborators: `if is_supervisor and collaborators: filter delegate`
   - Single agents and supervisors without collaborators: no filtering applied
   - Result: NO Lambda handler, NO OpenAPI endpoint for delegate action

3. **Resource Identification with bedsheet- Prefix**
   - Added `bedsheet-` prefix to infrastructure resources for easy identification
   - IAM roles: `bedsheet-${local.name_prefix}-agent-role`
   - IAM policies: `bedsheet-${local.name_prefix}-agent-permissions`
   - Lambda functions (when generated): `bedsheet-${local.name_prefix}-actions`
   - User-facing resources (Bedrock agents, aliases) kept clean without prefix

4. **Resource Tagging**
   - Fixed incorrect `agent_resource_tags` attribute → `tags` (correct Terraform syntax)
   - Added comprehensive tags to ALL resources:
     - `ManagedBy = "Bedsheet"`
     - `BedsheetVersion = "0.4.0"`
     - `Project = var.project_name`
     - `Environment = local.workspace`
     - `AgentType = "Supervisor|Collaborator|SingleAgent"` (for Bedrock agents)
   - Tags support governance, cost allocation, and resource filtering

5. **Verified with wisdom-council**
   - Generated deployment artifacts with all fixes applied
   - Confirmed NO Lambda files generated (delegate was only tool, filtered out)
   - Confirmed NO `/delegate` endpoint in openapi.yaml (only `/health`)
   - Confirmed `bedsheet-` prefix on IAM resources
   - Confirmed correct `tags` attribute in all resources

### Root Cause Analysis

**Problem:** User explicitly requested in previous session: "translate the @action decorator of bedsheet to the implementation in AWS, just as it does for GCP"

**What was happening:**
1. Supervisor auto-registers `delegate` action in `__init__()`
2. Introspection extracts ALL tools including delegate
3. AWS templates blindly generated Lambda + OpenAPI for ALL tools
4. Result: Redundant delegate Lambda that conflicts with Bedrock's native collaboration

**Solution:**
- Filter delegate at generation time for multi-agent scenarios
- Bedrock handles delegation via `aws_bedrockagent_agent_collaborator` resources
- GCP translates @actions to ADK tool stubs (platform idiom)
- AWS now translates by filtering delegate for supervisors (platform idiom)

### Files Modified

**Python Code (filtering logic):**
- `bedsheet/deploy/targets/aws.py:40-51` - Filter delegate before context creation
- `bedsheet/deploy/targets/aws_terraform.py:40-48` - Filter delegate before context creation

**Terraform Template (naming, tagging):**
- `bedsheet/deploy/templates/aws-terraform/main.tf.j2:40, 71` - bedsheet- prefix for IAM
- `bedsheet/deploy/templates/aws-terraform/main.tf.j2:195-201, 226-232, 296-302` - Fixed tags attribute

### Verification Results

Generated `wisdom-council/deploy/aws-terraform/`:
- ✅ 11 files generated (NO lambda directory)
- ✅ `openapi.yaml` contains only `/health` endpoint
- ✅ `main.tf` has NO Lambda resource definitions
- ✅ IAM resources named `bedsheet-wisdom_council-dev-agent-role`
- ✅ All resources properly tagged with ManagedBy=Bedsheet

### Next Steps (For Next Session)

1. **Deploy with Terraform** (blocked by aws-vault credentials issue)
   - Need to restart session for aws-vault to work properly
   - Run: `cd deploy/aws-terraform && aws-vault exec personal -- terraform plan`
   - Then: `aws-vault exec personal -- terraform apply`

2. **Test with Debug UI**
   - Start debug UI: `aws-vault exec personal -- python debug-ui/server.py`
   - Verify multi-agent collaboration works via Bedrock native delegation
   - Check traces show collaborator invocations (NOT Lambda delegate calls)

3. **Add to examples/** (if successful)
   - Copy wisdom-council to BedsheetAgents/examples/
   - Document as canonical multi-agent AWS deployment example

### Technical Debt Addressed

- ✅ AWS @action translation now matches user's original intent
- ✅ Resource naming conventions established (bedsheet- prefix)
- ✅ Resource tagging strategy implemented
- ✅ Multi-agent translation correctly handles platform idioms

---

## Session Summary (2025-12-12 Afternoon)

### What Was Done

1. **AWS Bedrock Debug UI - COMPLETE!**
   - Built comprehensive debug UI for AWS Bedrock agents
   - FastAPI server that proxies to Bedrock Agent Runtime API
   - SSE streaming for real-time event updates
   - Multi-agent collaboration tracing (collaborator_start/complete)
   - Tested with Judge/Sage/Oracle multi-agent system

2. **Debug UI Features**
   - Collapsible event items with badge icons and summaries
   - Thinking/rationale trace visualization
   - Tool call and result tracking
   - Environment variable configuration for agent ID/alias
   - Filter out redundant long thinking events (final synthesis)

3. **Template Updates**
   - Lambda handler simplified to use standard library only (removed aws_lambda_powertools dependency)
   - CDK stack improvements for multi-agent deployments
   - Debug UI template added to AWS target
   - Events panel now starts collapsed for cleaner UX

4. **AWS E2E Test Complete**
   - Successfully deployed agent to Bedrock via CDK
   - Invoked agent through debug UI
   - Verified multi-agent orchestration tracing works

### Files Modified

- `bedsheet/deploy/templates/aws/debug-ui/server.py.j2` - Debug UI server
- `bedsheet/deploy/templates/aws/lambda/handler.py.j2` - Simplified handler
- `bedsheet/deploy/templates/aws/stacks/agent_stack.py.j2` - CDK improvements

### Remaining for v0.4 GA

- Add Bedsheet @action compilation to Lambda (pending)
- Update roadmap: AWS Debug UI now DONE (was deferred)

---

## Session Summary (2025-12-10 Evening)

### What Was Done

1. **GCP ADK Dev UI Integration - WORKING!**
   - Fixed ADK agent discovery: `adk web .` (not `adk web agent`)
   - Added `root_agent` export to `__init__.py.j2` template
   - ADK requires agent directory structure with `root_agent` variable

2. **Gemini Model Compatibility Testing**
   - Tested multiple models for free-tier API key support
   - `gemini-2.0-flash` - quota errors (regional restrictions)
   - `gemini-1.5-flash` - also didn't work
   - `gemini-2.5-flash` - **WORKS with free tier!**
   - `gemini-3-pro-preview` - requires billing
   - Updated default model in `config.py` to `gemini-2.5-flash`

3. **Improved Developer Experience**
   - Added QUICK START guide to `.env.example` template
   - Clear instructions: get API key → copy .env → run `make dev-ui-local`
   - Updated CLI to show GCP-specific next steps after `bedsheet generate`

4. **Template Fixes**
   - `Makefile.j2`: Fixed `dev-ui-local` target to use `adk web .`
   - `__init__.py.j2`: Export `root_agent` for ADK discovery
   - `env.example.j2`: Added step-by-step QUICK START comments

### Files Modified

- `bedsheet/deploy/config.py` - Default model → `gemini-2.5-flash`
- `bedsheet/deploy/templates/gcp/Makefile.j2` - `adk web .` fix
- `bedsheet/deploy/templates/gcp/__init__.py.j2` - `root_agent` export
- `bedsheet/deploy/templates/gcp/env.example.j2` - QUICK START guide
- `bedsheet/cli/main.py` - GCP next steps in CLI output

---

## Session Summary (2025-12-08 Evening)

### What Was Done

1. **Published v0.4.0rc4 to PyPI** - End-to-end tested and working!
   - `bedsheet init myagent` scaffolds complete project
   - `bedsheet generate --target local` creates Docker deployment
   - `make build && make run` deploys working agent with real LLM calls

2. **Fixed Local Deploy Template Issues**
   - Dockerfile: Use `uv pip install -r pyproject.toml` (not editable install)
   - docker-compose: Build context from project root, proper volume mounts
   - app.py: Correct `agent.invoke(session_id, message)` signature
   - app.py: Use `CompletionEvent.response` (not `.text`)

3. **Removed build-system from Scaffolded Projects**
   - Agent projects aren't installable packages, just dependency declarations
   - Fixes `uv sync` / `uv run` errors with hatchling

4. **Release Candidates Published**
   - rc1: Initial CLI deps fix
   - rc2: CLI deps in main dependencies
   - rc3: Wired up agent invocation
   - rc4: Fixed session_id, event attributes, volume mounts

---

## Session Summary (2025-12-08 Morning)

### What Was Done

1. **v0.4 "Build Once, Deploy Anywhere"** - Full implementation on development branch
   - CLI: `bedsheet init`, `bedsheet generate`, `bedsheet validate`, `bedsheet deploy`
   - 3 deployment targets: Local (Docker), GCP (Terraform), AWS (CDK)
   - Multi-environment support: dev → staging → prod
   - GitHub Actions CI/CD for both GCP and AWS

2. **GCP Target Generator**
   - ADK-compatible `agent.py` generation
   - Terraform IaC (Cloud Run, IAM, Secret Manager)
   - GitHub Actions with Terraform workspaces
   - cloudbuild.yaml for Cloud Build

3. **AWS Target Generator**
   - AWS CDK stack (Bedrock Agent, Lambda, IAM)
   - Lambda handlers with AWS Powertools
   - OpenAPI schema generation from @action decorators
   - GitHub Actions with CDK contexts

4. **Local Target Generator**
   - Docker Compose + FastAPI wrapper
   - Hot reload support
   - Redis for session persistence

5. **Agent Introspection API**
   - `extract_agent_metadata()` for deployment compilation
   - Tool schema extraction from @action decorators

### Files Created (v0.4 branch)

```
bedsheet/
├── cli/
│   ├── __init__.py
│   └── main.py              # Typer CLI
├── deploy/
│   ├── config.py            # bedsheet.yaml Pydantic schema
│   ├── introspect.py        # Agent metadata extraction
│   └── targets/
│       ├── base.py          # DeploymentTarget protocol
│       ├── local.py         # Docker/FastAPI
│       ├── gcp.py           # ADK/Terraform
│       └── aws.py           # CDK/Bedrock
│   └── templates/
│       ├── local/           # 6 Jinja2 templates
│       ├── gcp/             # 13 Jinja2 templates
│       └── aws/             # 12 Jinja2 templates
```

---

## Version History

### v0.3.0 Features (Released)

| Feature | Status | Notes |
|---------|--------|-------|
| Structured Outputs | ✅ Done | OutputSchema from Pydantic or dict |
| Anthropic Beta Integration | ✅ Done | structured-outputs-2025-11-13 |
| LLMResponse.parsed_output | ✅ Done | Validated structured data |
| MockLLMClient support | ✅ Done | Testing with output schemas |
| Optional Redis Import | ✅ Done | Works without redis installed |

### v0.2.0 Features (Released)

| Feature | Status | Notes |
|---------|--------|-------|
| Supervisor Agent | ✅ Done | Extends Agent, manages collaborators |
| Supervisor Mode | ✅ Done | Orchestration with synthesis |
| Router Mode | ✅ Done | Direct handoff, no synthesis |
| Parallel Delegation | ✅ Done | Delegate to multiple agents at once |
| Multi-Agent Events | ✅ Done | RoutingEvent, DelegationEvent, etc. |

### v0.1.0 Features (Released)

| Feature | Status | Notes |
|---------|--------|-------|
| Single Agent with ReAct loop | ✅ Done | `Agent` class with tool calling |
| ActionGroup + @action decorator | ✅ Done | Auto schema inference |
| Streaming Events | ✅ Done | 11 event types |
| Parallel Tool Execution | ✅ Done | asyncio.gather |
| Pluggable Memory | ✅ Done | InMemory, RedisMemory |
| AnthropicClient | ✅ Done | Claude integration |

---

## Roadmap

### v0.4: Build Once, Deploy Anywhere (In Development)

| Feature | Status | Notes |
|---------|--------|-------|
| CLI (`bedsheet` command) | ✅ Done | init, generate, validate, deploy |
| bedsheet.yaml config schema | ✅ Done | Pydantic validation |
| Agent introspection API | ✅ Done | Extract metadata from agents |
| Local target (Docker) | ✅ Done | FastAPI + Docker Compose |
| GCP target (Terraform) | ✅ Done | ADK + Cloud Run + Terraform |
| AWS target (CDK) | ✅ Done | Bedrock + Lambda + CDK |
| GitHub Actions CI/CD | ✅ Done | Multi-environment workflows |
| Multi-env (dev/staging/prod) | ✅ Done | Terraform workspaces / CDK contexts |
| **1. Streaming SSE endpoint** | ✅ Done | `/invoke/stream` exposes Bedsheet's event stream |
| **2. Debug UI (React SPA)** | ✅ Done | Chat + live event stream + expand/collapse |
| 2a. Debug UI: Local target | ✅ Done | Included by default, env flag to disable |
| 2b. Debug UI: GCP Cloud Run | ✅ Done | ADK Dev UI via `make dev-ui-local` |
| 2c. Debug UI: AWS Bedrock | ✅ Done | FastAPI proxy to Bedrock Agent Runtime with tracing |
| **3. GCP Cloud Run E2E Test** | 🔲 TODO | Deploy real agent, verify API works (use Debug UI) |
| **4. AWS Bedrock E2E Test** | ✅ Done | Deployed Judge/Sage/Oracle, verified via Debug UI |

**Branch:** `development/v0.4-deploy-anywhere`
**Tests:** 179 passing (52 new for deployment)

**Before v0.4.0 GA:**
- Both GCP and AWS targets must be deployed and tested end-to-end with a real agent
- Debug UI with streaming for local and GCP targets

### v0.5: Knowledge & Safety (Planned)

| Feature | Status | Priority |
|---------|--------|----------|
| Knowledge Base Protocol | 🔮 Planned | High |
| RAG Integration | 🔮 Planned | High |
| Guardrails Protocol | 🔮 Planned | Medium |
| Content Filtering | 🔮 Planned | Medium |
| PII Detection | 🔮 Planned | Low |

### v0.6: GCP Agent Engine Target (Planned)

| Feature | Status | Priority |
|---------|--------|----------|
| Agent Engine deployment target | 🔮 Planned | High |
| A2A protocol support | 🔮 Planned | High |
| Managed sessions/memory | 🔮 Planned | Medium |
| ADK wrapper generation | 🔮 Planned | Medium |

**Why:** Agent Engine provides built-in A2A (Agent-to-Agent) protocol, managed session state, enterprise security (VPC-SC, CMEK), and interop with other enterprise agents (SAP Joule, Microsoft Copilot, etc.). Cloud Run remains the "flexible" option; Agent Engine is the "managed" option.

### v0.7: Advanced Features (Planned)

| Feature | Status | Priority |
|---------|--------|----------|
| AMAZON.UserInput equivalent | 🔮 Planned | Medium |
| Code Interpreter | 🔮 Planned | Medium |
| Inline Agents (runtime config) | 🔮 Planned | Low |
| MCP Integration | 🔮 Planned | Low |

---

## Deferred Tasks

Tasks identified but postponed for future consideration:

| Task | Reason | Priority |
|------|--------|----------|
| ASP Terraform Module Integration | Use Agent Starter Pack's battle-tested Terraform modules as optional `terraform_source: "asp"` | Medium |
| Observability Templates | Cloud Trace, Logging dashboards pre-configured | Low |
| Load Testing Integration | Locust templates like ASP | Low |
| Azure Target | Add Azure Bot Framework / Azure OpenAI target | Low |

---

## Architecture

```
bedsheet/
├── __init__.py              # Exports: Agent, Supervisor, ActionGroup
├── __main__.py              # Demo: python -m bedsheet
├── agent.py                 # Single agent with ReAct loop
├── supervisor.py            # Multi-agent coordination
├── action_group.py          # @action decorator, tool registration
├── events.py                # 11 event types for streaming
├── exceptions.py            # Custom exceptions
├── testing.py               # MockLLMClient for tests
├── llm/
│   ├── base.py              # LLMClient protocol
│   └── anthropic.py         # Claude integration
├── memory/
│   ├── base.py              # Memory protocol
│   ├── in_memory.py         # Dict-based (dev)
│   └── redis.py             # Redis-based (prod)
├── cli/                     # NEW in v0.4
│   └── main.py              # Typer CLI app
└── deploy/                  # NEW in v0.4
    ├── config.py            # bedsheet.yaml schema
    ├── introspect.py        # Agent metadata extraction
    ├── targets/             # Deployment generators
    └── templates/           # Jinja2 templates
```

---

## Design Decisions Log

### v0.4 Decisions

1. **AWS CDK over Terraform for AWS** - CDK is Pythonic, has native Bedrock L2 constructs, and generates CloudFormation (ejectable)
2. **Terraform for GCP** - GCP has no Python CDK equivalent; Terraform is industry standard
3. **Reuse, don't reinvent** - Designed to integrate with ASP's Terraform modules (deferred)
4. **User-choice ejectability** - Users can choose managed (Bedrock, Agent Engine) or ejectable (containers, serverless)
5. **Multi-environment via workspaces/contexts** - Terraform workspaces for GCP, CDK contexts for AWS

### v0.3 Decisions

1. **Structured Outputs via Anthropic Beta** - Use constrained decoding for 100% schema compliance
2. **Pydantic integration** - OutputSchema.from_pydantic() for familiar DX

### v0.2 Decisions

1. **Supervisor IS-A Agent** - Extend Agent rather than separate class hierarchy
2. **Single delegate tool** - Match AWS's AgentCommunication::sendMessage pattern
3. **Isolated memory** - Collaborators don't share supervisor's conversation

### v0.1 Decisions

1. **Bedrock-like API** - Mirror AWS Bedrock concepts for familiarity
2. **Streaming-first** - Async iterator with events, not batch responses
3. **Protocol-based extensibility** - Memory and LLMClient as protocols

---

## Links

- [GitHub Repository](https://github.com/sivang/bedsheet)
- [PyPI Package](https://pypi.org/project/bedsheet-agents/)
- [v0.4 Plan](~/.claude/plans/valiant-sniffing-origami.md)

---

**Copyright © 2025-2026 Sivan Grünberg, [Vitakka Consulting](https://vitakka.co/)**
