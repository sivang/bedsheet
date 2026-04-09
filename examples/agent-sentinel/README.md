# Agent Sentinel

Real-time AI agent security monitoring using [Bedsheet Sense](../../docs/sixth-sense-guide.html).

## Motivation

The OpenClaw crisis of Jan-Feb 2026 exposed critical gaps in AI agent security:

- **Rogue behavior**: Agent spammed 500+ messages after gaining iMessage access
- **Supply chain attacks**: 7.1% of ClawHub marketplace skills contained malicious code
- **API key leaks**: Moltbook breach exposed 1.5M API keys
- **Mass exposure**: 40,000+ unsecured agent instances on the public internet

Agent Sentinel demonstrates how a network of sentinel agents can monitor production AI agents for compromise, drift, and rogue behavior in real-time using PubNub.

## Architecture

**3 Worker Agents** (do real work):
- `web-researcher` — Performs DuckDuckGo searches
- `scheduler` — Manages a JSON calendar file
- `skill-acquirer` — Installs Python skills from a local ClawHub registry with SHA-256 verification

**2 Sentinel Agents** (monitor workers):
- `behavior-sentinel` — Reads the shared activity log, detects output rate anomalies
- `supply-chain-sentinel` — Re-hashes installed skills, detects malicious installs

**1 Commander** (correlates and responds):
- `sentinel-commander` — Listens for alerts, queries sentinels, issues quarantine orders

Each worker has a ~15% chance per cycle of going "rogue" — the web researcher spams searches, the scheduler sabotages the calendar, the skill acquirer installs a known-malicious skill. Sentinels detect this through real file I/O and alert the commander over PubNub.

## Quick Start

This project was scaffolded with `bedsheet init` and uses the Bedsheet CLI tooling:

```bash
# 1. Install Bedsheet with Sense module and search dependency
uv pip install bedsheet[sense] duckduckgo-search

# 2. Validate the project configuration
cd examples/agent-sentinel
bedsheet validate

# 3. Set environment variables
export PUBNUB_SUBSCRIBE_KEY=sub-c-...
export PUBNUB_PUBLISH_KEY=pub-c-...
export ANTHROPIC_API_KEY=sk-ant-...

# 4. Run the demo
python run.py
```

## Using the Bedsheet CLI

This project includes a `bedsheet.yaml` that defines all 6 agents. You can use the full Bedsheet CLI workflow:

```bash
# Validate the configuration
bedsheet validate
# ✓ Configuration is valid!
# Project: agent-sentinel
# Agents: 6

# Generate deployment artifacts (e.g., for local Docker)
bedsheet generate --target local

# Or generate for cloud deployment
bedsheet generate --target gcp
bedsheet generate --target aws
```

### Creating Your Own Sentinel Project

To start a new project from scratch using the Bedsheet CLI:

```bash
# Scaffold a new project
bedsheet init my-sentinel-network

# Customize agents/ with your own worker and sentinel agents
# Edit bedsheet.yaml to register your agents

# Validate and generate
bedsheet validate
bedsheet generate --target local
```

## What to Expect

1. Workers come online and start doing real work (searching, scheduling, installing skills)
2. Randomly (~15% per cycle), a worker goes rogue
3. Sentinels detect the anomaly through real file reads:
   - Behavior sentinel sees the activity rate spike in `data/activity_log.jsonl`
   - Supply chain sentinel sees the malicious skill in `data/installed_skills/`
4. Sentinels broadcast alert signals over PubNub
5. Commander claims the incident, queries sentinels for evidence, issues quarantine

## Files

```
agent-sentinel/
├── bedsheet.yaml             # Bedsheet CLI configuration
├── pyproject.toml            # Dependencies
├── run.py                    # Subprocess launcher
├── data/
│   └── calendar.json         # Pre-seeded appointments
├── clawhub/
│   ├── registry.json         # Skill hashes + malicious flags
│   ├── weather_lookup.py     # Legit skill
│   ├── sentiment_analyzer.py # Legit skill
│   └── data_exfiltrator.py   # Known-malicious (inert)
└── agents/
    ├── web_researcher.py     # Worker
    ├── scheduler.py          # Worker
    ├── skill_acquirer.py     # Worker
    ├── behavior_sentinel.py  # Sentinel
    ├── supply_chain_sentinel.py  # Sentinel
    └── sentinel_commander.py # Commander
```
