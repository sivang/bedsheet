# Bedsheet Agents - Project Status

## Current Version: v0.3.0 🚀 Published on PyPI

**Last Session:** 2025-12-08

### Release Status

| Version | Status | Branch |
|---------|--------|--------|
| v0.3.0 | ✅ Released on PyPI | main |
| v0.4.0 | 🚧 In Development | development/v0.4-deploy-anywhere |

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

## Session Summary (2025-12-08)

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

**Branch:** `development/v0.4-deploy-anywhere`
**Tests:** 179 passing (52 new for deployment)

### v0.5: Knowledge & Safety (Planned)

| Feature | Status | Priority |
|---------|--------|----------|
| Knowledge Base Protocol | 🔮 Planned | High |
| RAG Integration | 🔮 Planned | High |
| Guardrails Protocol | 🔮 Planned | Medium |
| Content Filtering | 🔮 Planned | Medium |
| PII Detection | 🔮 Planned | Low |

### v0.6: Advanced Features (Planned)

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
