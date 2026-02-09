"""Cloud Monitor - launches all agents as separate processes.

Each agent runs in its own process with its own PubNub connection,
demonstrating true distributed agent communication.

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

AGENTS = [
    "agents/cpu_watcher.py",
    "agents/memory_watcher.py",
    "agents/log_analyzer.py",
    "agents/security_scanner.py",
    "agents/incident_commander.py",
]

REQUIRED_ENV = ["PUBNUB_SUBSCRIBE_KEY", "PUBNUB_PUBLISH_KEY", "ANTHROPIC_API_KEY"]


def main():
    # Check environment
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
    processes: list[subprocess.Popen] = []

    print("=" * 60)
    print("  Cloud Monitor - Bedsheet Sense Demo")
    print("  Launching 5 distributed agents...")
    print("=" * 60)

    try:
        for agent_script in AGENTS:
            full_path = os.path.join(script_dir, agent_script)
            agent_name = os.path.basename(agent_script).replace(".py", "").replace("_", "-")
            print(f"  Starting {agent_name}...")

            proc = subprocess.Popen(
                [sys.executable, full_path],
                env=os.environ.copy(),
                stdout=sys.stdout,
                stderr=sys.stderr,
            )
            processes.append(proc)
            time.sleep(1)  # Stagger startup for clean PubNub connects

        print("=" * 60)
        print("  All agents online! Press Ctrl+C to stop.")
        print("=" * 60)

        # Wait for any process to exit or for keyboard interrupt
        while all(p.poll() is None for p in processes):
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nShutting down agents...")
    finally:
        for proc in processes:
            if proc.poll() is None:
                proc.send_signal(signal.SIGINT)

        # Give agents time for graceful shutdown
        time.sleep(2)

        for proc in processes:
            if proc.poll() is None:
                proc.terminate()

        print("All agents stopped.")


if __name__ == "__main__":
    main()
