# Bedsheet Agents - Project Status

## Current Version: v0.4.7 (released)

**Last Session:** 2026-01-22

### Release Status

| Version | Status | Branch |
|---------|--------|--------|
| v0.3.0 | ✅ Released on PyPI | main |
| v0.4.0 | ✅ Released on PyPI | main |
| v0.4.2 | ✅ Released on PyPI | main |
| v0.4.3 | ✅ Released on PyPI | main |
| v0.4.4 | ✅ Released on PyPI | main |
| v0.4.5 | ✅ Released on PyPI | main |
| v0.4.6 | ✅ Released on PyPI | main |
| v0.4.7 | ✅ Released on PyPI | main |

### Release Artifacts

| Artifact | Status |
|----------|--------|
| Source Code | ✅ Complete |
| Test Suite | ✅ 265 tests passing |
| README.md | ✅ Comprehensive with examples |
| CHANGELOG.md | ✅ v0.1.0-v0.4.0 documented |
| CONTRIBUTING.md | ✅ Contributor guidelines |
| LICENSE | ✅ Elastic License 2.0 (Sivan Grünberg, Vitakka Consulting) |
| CI/CD | ✅ GitHub Actions (test, lint, typecheck) |
| Documentation | ✅ User Guide + Technical Guide + Multi-agent Guide |
| Examples | ✅ Investment advisor demo |
| Demo | ✅ `uvx bedsheet demo` (requires API key, uses REAL DATA from Yahoo Finance + DuckDuckGo) |
| pyproject.toml | ✅ PyPI ready |

---

## Roadmap

### v0.5.0 - Custom UIs & Enhanced Examples

| Feature | Priority | Status |
|---------|----------|--------|
| **Investment Advisor Custom UI** | High | 📋 Planned |
| - Stock price charts (candlestick/line) | | |
| - Technical indicator gauges (RSI, MACD) | | |
| - Risk assessment meters | | |
| - Sentiment analysis display | | |
| - Recommendation cards with confidence | | |
| Example: Customer Support Agent | Medium | 📋 Planned |
| Example: Code Review Agent | Medium | 📋 Planned |

### Future Considerations

- AWS Bedrock target improvements
- Azure OpenAI target
- Local LLM support (Ollama)

---

## Session Summary (2026-01-22 Night) - REAL DATA Implementation + GitHub Release "Hermes"

### What Was Done

1. **Replaced ALL Mock Data with REAL APIs**
   - All 3 demo locations now use real data (no mocks, no simulations)
   - **Yahoo Finance** (yfinance): Stock prices, PE ratios, market caps, 52-week ranges
   - **DuckDuckGo** (ddgs): Real news articles with sources and dates
   - **Calculated metrics**: RSI-14, MACD, SMA-20/50, beta vs SPY, volatility, max drawdown, Sharpe ratio

2. **GitHub Release v0.4.7 "Hermes" Published**
   - Codename: Hermes (swift messenger god = deploy anywhere)
   - URL: https://github.com/sivang/bedsheet/releases/tag/v0.4.7
   - Comprehensive release notes with real data capabilities

3. **Dependencies Added**
   - `yfinance>=0.2.40` - Yahoo Finance (no API key required)
   - `ddgs>=6.0.0` - DuckDuckGo search (no API key required)
   - Available via: `pip install bedsheet[demo]`

4. **Verified with Real Data**
   - NVDA: $184.61, RSI 47.09, Beta 1.84, 5 real news articles
   - AAPL: $249.03, RSI 13.77 (oversold), Beta 1.26
   - All 265 tests passing

### Files Modified

| File | Changes |
|------|---------|
| `bedsheet/__main__.py` | Real data tools for `uvx bedsheet demo` |
| `examples/investment-advisor/agents.py` | Real yfinance/ddgs tools |
| `examples/investment-advisor/deploy/gcp/agent/agent.py` | Real tools for GCP deployment |
| `examples/investment-advisor/deploy/gcp/pyproject.toml` | Added yfinance, ddgs deps |
| `examples/investment-advisor/pyproject.toml` | Added yfinance, ddgs deps |
| `pyproject.toml` | Added `[demo]` optional dependency group |

---

## Session Summary (2026-01-22 Evening) - DX Safeguards + make ui + E2E Complete

### What Was Done

1. **Released v0.4.3 through v0.4.7** - Six releases in one session!

   | Version | Feature |
   |---------|---------|
   | v0.4.3 | Dynamic CLI version (importlib.metadata) |
   | v0.4.4 | Credential preflight check (warns if GOOGLE_APPLICATION_CREDENTIALS set) |
   | v0.4.5 | Project consistency check (terraform.tfvars vs gcloud config) |
   | v0.4.6 | `make ui` command (one-command Dev UI access) |
   | v0.4.7 | Improved first-time UX (check cloud-run-proxy component) |

2. **Complete E2E Testing Validated**
   - Fresh agent with `uvx bedsheet@latest init test-agent`
   - Generated with `bedsheet generate --target gcp`
   - Deployed to Cloud Run (since deleted)
   - Dev UI accessible via `make ui` at `http://localhost:8080/dev-ui/`

3. **Documentation Mega Update**
   - Updated `docs/gcp-deployment-deep-dive.md` with:
     - New DX Safeguards section
     - Testing Deployed Agents section
     - Release History section
     - Executive Summary for stakeholders
   - Updated PROJECT_STATUS.md with current session

### Key Philosophy Quote

> "Every time something happens and you are setting something manually instead of analyzing and providing a solution...you are leaving a bug to explore in the user's hands."

This session embodied this principle by converting manual workarounds into automated safeguards.

### Files Modified

| File | Changes |
|------|---------|
| `bedsheet/deploy/templates/gcp/Makefile.j2` | Credential check, project check, `make ui` |
| `bedsheet/deploy/templates/gcp/DEPLOYMENT_GUIDE.md.j2` | Warning documentation |
| `bedsheet/cli/main.py` | Dynamic version via importlib.metadata |
| `docs/gcp-deployment-deep-dive.md` | Comprehensive update |
| `PROJECT_STATUS.md` | Session summary |
| `pyproject.toml` | Version 0.4.7 |
| `CHANGELOG.md` | v0.4.3-v0.4.7 entries |

---

## Session Summary (2026-01-22 Morning) - GCP E2E SUCCESS + Documentation

### What Was Done

1. **Fixed GCP E2E Testing - ROOT CAUSE FOUND!**
   - `GOOGLE_APPLICATION_CREDENTIALS` env var pointed to wrong project's service account
   - Python SDK prioritizes this env var over ADC
   - Fix: `unset GOOGLE_APPLICATION_CREDENTIALS`

2. **Investment Advisor Deployed to Cloud Run**
   - Deployed to Cloud Run (since deleted)
   - Model: `gemini-3-flash-preview` via global Vertex AI endpoint
   - Multi-agent system working: MarketAnalyst, NewsResearcher, RiskAnalyst
   - All tools functional

3. **ADK Dev UI Enabled**
   - Changed Dockerfile template from `api_server` to `web` mode
   - Dev UI accessible at `/dev-ui/` on both local and Cloud Run

4. **Comprehensive Documentation Created**
   - `docs/gcp-deployment-deep-dive.md` and `.html`
   - Architecture diagrams, troubleshooting guides, credential flow explanations
   - Sanitized sensitive info from docs and git history

### Key Technical Insight

**SDK Credential Priority:**
1. `GOOGLE_APPLICATION_CREDENTIALS` env var (highest priority)
2. Application Default Credentials (ADC)
3. Compute Engine / Cloud Run service account

If `GOOGLE_APPLICATION_CREDENTIALS` points to project A's SA, but you're accessing project B, you get 403 even with correct IAM roles.

### Files Modified

| File | Changes |
|------|---------|
| `bedsheet/deploy/templates/gcp/Dockerfile.j2` | Use `web` mode for Dev UI |
| `docs/gcp-deployment-deep-dive.md` | New comprehensive docs |
| `docs/gcp-deployment-deep-dive.html` | Styled HTML version |

---

## Session Summary (2026-01-21) - GCP ADC Auth Improvements + E2E Test Progress

### What Was Done

1. **GCP Templates Updated for ADC (Application Default Credentials)**
   - Removed API key requirement - now uses user's GCP credentials
   - `make init` auto-triggers browser auth if needed
   - ADC quota project set explicitly to target project
   - GOOGLE_CLOUD_PROJECT passed to all Terraform commands

2. **Removed google_project_service from Terraform**
   - APIs now enabled via gcloud CLI in Makefile (avoids ADC permission issues)
   - Terraform focuses on resource creation only
   - Fixed dependency issues between resources

3. **Added IAM API to enabled services**
   - Prevents permission errors during service account creation

4. **Published Multiple Release Candidates**
   - v0.4.2rc3: Initial ADC changes
   - v0.4.2rc4: Quota project + ADC validation
   - v0.4.2rc5: Removed google_project_service from Terraform

5. **GCP E2E Test Progress**
   - search-assistant agent configured with Google Search grounding
   - Authentication working (gcloud auth + ADC)
   - APIs enabled successfully
   - Terraform still encountering permission issues (ADC vs gcloud auth difference)

### Key Technical Insight

**ADC vs gcloud CLI auth difference:**
- `gcloud auth login` → full account permissions for gcloud CLI
- `gcloud auth application-default login` → limited OAuth scopes for SDKs
- Terraform google provider uses ADC, which has fewer permissions than gcloud CLI
- Solution: Enable APIs with gcloud, create resources with Terraform

### Files Modified

| File | Changes |
|------|---------|
| `bedsheet/deploy/templates/gcp/Makefile.j2` | ADC validation, quota project, GOOGLE_CLOUD_PROJECT |
| `bedsheet/deploy/templates/gcp/main.tf.j2` | Removed google_project_service resources |
| `pyproject.toml` | Version bumped to 0.4.2rc5 |

### Pending Work

1. **Complete GCP E2E Test** - Terraform apply still failing, may need service account key
2. **Commit template changes** - All changes ready for commit
3. **Release v0.4.2** - After E2E validation

### Next Steps

Option A: Use service account key for Terraform (traditional approach)
Option B: Further investigate ADC permission scopes
Option C: Test with user who has simpler GCP setup

---

## Session Summary (2026-01-18) - AgentCore Target + Strands Comparison

### What Was Done

1. **AgentCore Deployment Target - COMPLETE! (EXPERIMENTAL)**
   - Added new `agentcore` target for Amazon Bedrock AgentCore
   - ⚠️ **Experimental**: AgentCore is in preview, APIs may change
   - Full stack: Runtime + Gateway + Lambda for tools
   - Terraform-based infrastructure
   - 16 template files created
   - 26 unit tests added (all passing)

2. **Strands vs Bedsheet Research**
   - Comprehensive feature comparison analysis
   - Strands has more features: Swarms, Graphs, Workflows, multi-provider LLM
   - Bedsheet has unique strengths: multi-cloud deployment, CLI, structured outputs
   - Decision: Keep Bedsheet simple, document patterns

3. **Multi-Agent Patterns Documentation**
   - Created `docs/multi-agent-patterns.md`
   - Shows how to implement Swarms, Graphs, Workflows, A2A with current constructs
   - No new features needed - just creative use of Supervisor + @action + asyncio

4. **Roadmap Update**
   - Added "Advanced Orchestration (v0.9+)" section
   - ReWOO, Reflexion, Autonomous Loops planned for future
   - Multi-agent patterns documented as achievable today

### Files Created

| File | Description |
|------|-------------|
| `bedsheet/deploy/targets/agentcore.py` | AgentCore target implementation |
| `bedsheet/deploy/templates/agentcore/` | 16 Jinja2 templates |
| `tests/test_deploy_targets_agentcore.py` | 26 unit tests |
| `docs/multi-agent-patterns.md` | Pattern implementation guide |
| `docs/strands-advanced-patterns.md` | Detailed pattern explanations |

### Files Modified

| File | Changes |
|------|---------|
| `bedsheet/deploy/config.py` | Added `AgentCoreTargetConfig` |
| `bedsheet/deploy/__init__.py` | Exported new config class |
| `bedsheet/deploy/targets/__init__.py` | Exported `AgentCoreTarget` |
| `bedsheet/cli/main.py` | Added `agentcore` to TARGETS |
| `PROJECT_STATUS.md` | Updated roadmap with orchestration styles |

### Branch

`feature/agentcore-target` - Ready for merge

---

## Session Summary (2026-01-07) - Post-Release Polish & Roadmap Update

### What Was Done

1. **Package Rename: bedsheet-agents → bedsheet**
   - Simplified PyPI package name for cleaner `uvx bedsheet` experience
   - Updated pyproject.toml package name

2. **CLI Demo Command**
   - Added `bedsheet demo` command to CLI
   - Fixes "Missing command" error when running `uvx bedsheet`
   - Demo runs the multi-agent investment advisor

3. **Documentation Updates (pip → uv)**
   - Updated all documentation to use modern `uv`/`uvx` tooling
   - Files updated: README.md, CONTRIBUTING.md, CLAUDE.md, PROJECT_STATUS.md
   - Files updated: docs/user-guide.md, docs/user-guide.html, bedsheet/cli/README.md

4. **Multi-Agent Guide HTML**
   - Created HTML version of multi-agent-guide.md
   - Matches styling of other documentation files

5. **README Image Optimization**
   - Updated image from logo.png to Pythonic.jpg
   - Optimized file size: 3.9MB → 652KB (JPEG 85% quality)
   - No visible quality loss

6. **Git History Cleanup**
   - Removed all Claude attributions from commit messages
   - Used git-filter-repo for safe history rewrite
   - Verified integrity via tree hash comparison before force push

7. **Project Conventions**
   - Created `.claude/rules/dont.md` with lessons learned
   - Documents: image backup before edits, GitHub Pages links, no Claude attributions

8. **Roadmap Update**
   - Enhanced v0.6: Added "classification models for high-speed validation"
   - Added v0.8: WASM/Spin support (browser agents, edge deployment, Fermyon Cloud)

### Commits

```
52aad0d Reduce size even more
c7344f7 chore: optimize README image size (3.9MB → 652KB)
82a4a6d chore: crop README image to 16:9 widescreen
9cf81f2 feat(cli): add demo command and update README image
e308f35 docs: update remaining files to use uv tooling
09d2caf docs: update README to use uvx/uv instead of pip
798b5ff docs: add HTML version of multi-agent guide
7c885a5 chore: rename package from bedsheet-agents to bedsheet
dd7fb6d Fix link format for LICENSE in README.md
059f2bd Update LICENSE link to LICENSE.md
```

### Files Modified

**Python Code:**
- `bedsheet/cli/main.py` - Added demo command, version bump to 0.4.0
- `pyproject.toml` - Package rename

**Documentation:**
- `README.md` - uv tooling, new image, roadmap update
- `CONTRIBUTING.md` - uv tooling
- `CLAUDE.md` - uv tooling
- `docs/user-guide.md` - uv tooling
- `docs/user-guide.html` - uv tooling
- `docs/multi-agent-guide.html` - New file
- `bedsheet/cli/README.md` - uv tooling

**Assets:**
- `Pythonic.jpg` - New optimized README image (652KB)

**Local Config:**
- `.claude/rules/dont.md` - Project conventions (not committed)

---

## Session Summary (2026-01-01) - v0.4.0 GA Release!

### What Was Done

1. **Published v0.4.0 to PyPI** - GA Release!
   - Bumped version from 0.4.0rc4 to 0.4.0
   - Fixed build: Added node_modules exclusion to pyproject.toml
   - Removed all `--prerelease` flags from docs and templates
   - https://pypi.org/project/bedsheet/

2. **License Cleanup**
   - Updated all Apache 2.0 references to Elastic License 2.0
   - Files updated: PROJECT_STATUS.md, README.md, CONTRIBUTING.md, all HTML docs

3. **PR #1 Merged**
   - CI/CD fixes merged to main
   - All GitHub Actions passing (test 3.11, 3.12, lint, typecheck)

4. **uvx Support**
   - Package now installable via `uvx bedsheet --help`
   - No more `--prerelease` needed

### Install Options (Now Stable!)

```bash
uv pip install bedsheet
uv add bedsheet
uvx bedsheet --help
```

### Files Modified

- `pyproject.toml` - Version bump + build exclusions
- `docs/deployment-guide.html` - Removed --prerelease
- `bedsheet/deploy/templates/gcp/Dockerfile.j2` - Removed --prerelease
- `bedsheet/deploy/templates/local/Dockerfile.j2` - Removed --prerelease

### Next Steps (For v0.5)

1. **GCP Cloud Run E2E Test** - Still pending
2. **Knowledge bases and RAG** - v0.5 roadmap item
3. **Guardrails and safety** - v0.6 roadmap item

---

## Session Summary (2025-12-31 Evening)

### What Was Done

1. **AWS Terraform Thinking Events - COMPLETE!**
   - Solved thinking/rationale extraction for AWS Bedrock Debug UI
   - Option A prompt injection extracts XML `<thinking>` tags from model responses
   - Backported to Bedsheet templates: `aws-terraform/debug-ui/server.py.j2`
   - Fixed duplicate thinking events in UI (deduplication logic)
   - Fixed `<answer>` tag content appearing in thinking panel

2. **AWS Terraform Target - COMPLETE!**
   - Added `aws-terraform` target to CLI (`bedsheet/deploy/targets/aws_terraform.py`)
   - Updated CLI main.py to support aws-terraform in generate and deploy commands
   - Updated config.py to include aws-terraform in TargetType enum
   - Full E2E tested with wisdom-council multi-agent deployment

3. **Documentation Review - COMPLETE!**
   - Added comprehensive v0.4.0 entry to CHANGELOG.md
   - Reviewed README.md roadmap (already accurate)
   - Updated PROJECT_STATUS.md with session summaries
   - All documentation now reflects v0.4 features

### Files Modified

**Python Code:**
- `bedsheet/cli/main.py` - Added aws-terraform target
- `bedsheet/deploy/config.py` - Added aws-terraform to TargetType enum

**Templates:**
- `bedsheet/deploy/templates/aws-terraform/debug-ui/server.py.j2` - Thinking extraction

**Documentation:**
- `CHANGELOG.md` - Added v0.4.0 section
- `PROJECT_STATUS.md` - Updated session history

### Next Steps (For v0.4.0 GA)

1. **GCP Cloud Run E2E Test** - Still pending
2. **Final testing across all targets**
3. **Release v0.4.0 to PyPI**

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

### v0.4: Build Once, Deploy Anywhere (COMPLETE ✅)

**Latest:** v0.4.7 on PyPI

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
| Streaming SSE endpoint | ✅ Done | `/invoke/stream` exposes Bedsheet's event stream |
| Debug UI (React SPA) | ✅ Done | Chat + live event stream + expand/collapse |
| Debug UI: Local target | ✅ Done | Included by default, env flag to disable |
| Debug UI: GCP Cloud Run | ✅ Done | ADK Dev UI via `make ui` |
| Debug UI: AWS Bedrock | ✅ Done | FastAPI proxy to Bedrock Agent Runtime with tracing |
| GCP Cloud Run E2E Test | ✅ Done | test-agent deployed, Dev UI verified via `make ui` |
| AWS Bedrock E2E Test | ✅ Done | Deployed Judge/Sage/Oracle, verified via Debug UI |
| Credential preflight check | ✅ Done | v0.4.4 - warns if GOOGLE_APPLICATION_CREDENTIALS set |
| Project consistency check | ✅ Done | v0.4.5 - validates terraform.tfvars vs gcloud config |
| `make ui` command | ✅ Done | v0.4.6 - one-command access to deployed Dev UI |
| First-time UX improvements | ✅ Done | v0.4.7 - checks for cloud-run-proxy component |
| Real data demo tools | ✅ Done | v0.4.7 - yfinance + ddgs, no mocks |

**Tests:** 265 passing
**GitHub Release:** [v0.4.7 "Hermes"](https://github.com/sivang/bedsheet/releases/tag/v0.4.7)

### v0.5: Knowledge Bases, RAG (Planned)

| Feature | Status | Priority |
|---------|--------|----------|
| Knowledge Base Protocol | 🔮 Planned | High |
| RAG Integration | 🔮 Planned | High |
| Vector store abstraction | 🔮 Planned | Medium |

### v0.6: Guardrails, Safety (Planned)

| Feature | Status | Priority |
|---------|--------|----------|
| Classification models for high-speed validation | 🔮 Planned | High |
| Content Filtering | 🔮 Planned | Medium |
| PII Detection | 🔮 Planned | Medium |
| Prompt injection detection | 🔮 Planned | Medium |

**Approach:** Use lightweight classification models (not full LLMs) for input/output validation. Fast inference for real-time safety checks.

### v0.7: GCP Agent Engine, A2A Protocol (Planned)

| Feature | Status | Priority |
|---------|--------|----------|
| Agent Engine deployment target | 🔮 Planned | High |
| A2A protocol support | 🔮 Planned | High |
| Managed sessions/memory | 🔮 Planned | Medium |
| ADK wrapper generation | 🔮 Planned | Medium |

**Why:** Agent Engine provides built-in A2A (Agent-to-Agent) protocol, managed session state, enterprise security (VPC-SC, CMEK), and interop with other enterprise agents (SAP Joule, Microsoft Copilot, etc.). Cloud Run remains the "flexible" option; Agent Engine is the "managed" option.

### v0.8: WASM/Spin Support (Planned)

| Feature | Status | Priority |
|---------|--------|----------|
| Browser-based agents via WASM | 🔮 Planned | High |
| Edge deployment (Cloudflare Workers, Deno Deploy) | 🔮 Planned | High |
| Fermyon Spin deployment target | 🔮 Planned | High |
| Sandboxed tool execution | 🔮 Planned | Medium |
| Plugin system via WASM modules | 🔮 Planned | Low |

**Why:** WASM enables running agents in browsers, edge runtimes, and with near-instant cold starts. Spin provides serverless WASM deployment to Fermyon Cloud.

### Future: Advanced Orchestration (v0.9+)

| Feature | Description | Priority |
|---------|-------------|----------|
| **ReWOO** | Plan-Execute-Synthesize pattern (fewer LLM calls) | Medium |
| **Reflexion** | Self-critique and iterative improvement loop | Medium |
| **Autonomous Loops** | Long-running agents with checkpointing | Medium |

**Note:** Multi-agent patterns (Swarms, Graphs, Workflows, A2A) are already achievable with current constructs. See [docs/multi-agent-patterns.md](docs/multi-agent-patterns.md).

### Future: Advanced Features

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
├── __main__.py              # Demo: uvx bedsheet
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
- [PyPI Package](https://pypi.org/project/bedsheet/)
- [v0.4 Plan](~/.claude/plans/valiant-sniffing-origami.md)

---

**Copyright © 2025-2026 Sivan Grünberg, [Vitakka Consulting](https://vitakka.co/)**
