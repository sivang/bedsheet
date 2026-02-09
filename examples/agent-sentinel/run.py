"""Agent Sentinel - launches worker and sentinel agents as separate processes.

Workers start first (they produce the activity that sentinels monitor),
then sentinels, then the commander that correlates alerts.

Required environment variables:
    PUBNUB_SUBSCRIBE_KEY - PubNub subscribe key
    PUBNUB_PUBLISH_KEY   - PubNub publish key
    ANTHROPIC_API_KEY    - Anthropic API key for Claude

Usage:
    python run.py
"""

import os
import signal
import subprocess
import sys
import time

# Workers start first, then sentinels, then commander
AGENTS = [
    # Workers (produce real activity)
    "agents/web_researcher.py",
    "agents/scheduler.py",
    "agents/skill_acquirer.py",
    # Sentinels (monitor workers)
    "agents/behavior_sentinel.py",
    "agents/supply_chain_sentinel.py",
    # Commander (correlates alerts)
    "agents/sentinel_commander.py",
]

REQUIRED_ENV = ["PUBNUB_SUBSCRIBE_KEY", "PUBNUB_PUBLISH_KEY", "ANTHROPIC_API_KEY"]


def main():
    missing = [v for v in REQUIRED_ENV if not os.environ.get(v)]
    if missing:
        print("Missing required environment variables:")
        for v in missing:
            print(f"  {v}")
        print("\nSet them and try again:")
        print("  export PUBNUB_SUBSCRIBE_KEY=sub-c-...")
        print("  export PUBNUB_PUBLISH_KEY=pub-c-...")
        print("  export ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)

    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Ensure data directory exists and clean up previous run artifacts
    data_dir = os.path.join(script_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    log_path = os.path.join(data_dir, "activity_log.jsonl")
    if os.path.exists(log_path):
        os.remove(log_path)
    installed_dir = os.path.join(data_dir, "installed_skills")
    if os.path.exists(installed_dir):
        import shutil

        shutil.rmtree(installed_dir)

    processes: list[subprocess.Popen] = []

    print("=" * 60)
    print("  Agent Sentinel - AI Agent Security Monitoring")
    print("  Inspired by the OpenClaw crisis of 2026")
    print("  Launching 6 agents (3 workers + 2 sentinels + 1 commander)...")
    print("=" * 60)

    try:
        for agent_script in AGENTS:
            full_path = os.path.join(script_dir, agent_script)
            agent_name = (
                os.path.basename(agent_script).replace(".py", "").replace("_", "-")
            )
            print(f"  Starting {agent_name}...")

            proc = subprocess.Popen(
                [sys.executable, full_path],
                env=os.environ.copy(),
                stdout=sys.stdout,
                stderr=sys.stderr,
            )
            processes.append(proc)
            time.sleep(2)  # Stagger startup

        print("=" * 60)
        print("  All agents online! Workers are doing real work.")
        print("  Sentinels are watching. ~15% chance of rogue behavior per cycle.")
        print("  Press Ctrl+C to stop.")
        print("=" * 60)

        while all(p.poll() is None for p in processes):
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nShutting down agents...")
    finally:
        for proc in processes:
            if proc.poll() is None:
                proc.send_signal(signal.SIGINT)

        time.sleep(2)

        for proc in processes:
            if proc.poll() is None:
                proc.terminate()

        print("All agents stopped.")


if __name__ == "__main__":
    main()
