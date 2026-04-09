# Cloud Monitor - Bedsheet Sense Demo

Demonstrates distributed agent communication using Bedsheet's Sense module and PubNub.

Five agents run as **separate processes**, each with its own PubNub connection, communicating via signals over the network.

## Agents

| Agent | Role | Tools |
|-------|------|-------|
| `cpu-watcher` | Monitors CPU usage, alerts on spikes | `get_cpu_usage`, `get_process_top` |
| `memory-watcher` | Monitors RAM and swap | `get_memory_usage`, `get_swap_usage` |
| `log-analyzer` | Searches and analyzes logs | `tail_log`, `search_log`, `get_error_rate` |
| `security-scanner` | Scans ports and login attempts | `check_open_ports`, `check_failed_logins` |
| `incident-commander` | Coordinates responses to alerts | `request_remote_agent`, `broadcast_alert`, `list_online_agents` |

## Setup

1. Get free PubNub keys at https://www.pubnub.com (200 MAU free tier)

2. Set environment variables:
```bash
export PUBNUB_SUBSCRIBE_KEY=sub-c-...
export PUBNUB_PUBLISH_KEY=pub-c-...
export ANTHROPIC_API_KEY=sk-ant-...
```

3. Install dependencies:
```bash
pip install bedsheet[sense] psutil
```

4. Run:
```bash
python run.py
```

## How It Works

1. All agents connect to PubNub and subscribe to `alerts` and `tasks` channels
2. Worker agents (cpu-watcher, memory-watcher) monitor system metrics in a loop
3. When a metric crosses a threshold, the watcher broadcasts an `alert` signal
4. The incident-commander receives the alert, claims the incident, then:
   - Queries relevant agents via `request` signals
   - Each agent invokes its LLM + tools to gather data
   - Commander synthesizes findings into an incident report
