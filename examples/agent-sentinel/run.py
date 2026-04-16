"""Agent Sentinel - launches the Action Gateway + worker and sentinel agents.

Launch order: gateway first (owns all tool execution), then workers
(thin LLM shells that proxy tools through the gateway), then sentinels
(query the gateway's tamper-proof ledger), then the commander.

Required environment variables:
    PUBNUB_SUBSCRIBE_KEY - PubNub subscribe key
    PUBNUB_PUBLISH_KEY   - PubNub publish key
    GEMINI_API_KEY       - Gemini API key

Usage:
    python run.py
"""

import logging
import os
import select
import signal
import subprocess
import sys
import time


# ============================================================================
# Diagnostic Logging Setup (adapted from ZeteoAI)
# ============================================================================


class ColorFormatter(logging.Formatter):
    """Custom formatter with colors for terminal output."""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record):
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logging():
    """Configure diagnostic logging for the sentinel launcher."""
    logger = logging.getLogger("sentinel")
    logger.setLevel(logging.DEBUG)

    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)

    formatter = ColorFormatter(
        fmt="%(asctime)s | %(levelname)-17s | %(message)s", datefmt="%H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


logger = setup_logging()


def log_section(title: str):
    """Log a section divider."""
    logger.info(f"{'─' * 55}")
    logger.info(f"  {title}")
    logger.info(f"{'─' * 55}")


# Gateway first, then workers, then sentinels, then commander
AGENTS = [
    # Action Gateway (owns all tool execution — must start first)
    "middleware/action_gateway.py",
    # Workers (thin LLM shells, proxy tools through gateway)
    "agents/web_researcher.py",
    "agents/scheduler.py",
    "agents/skill_acquirer.py",
    # Sentinels (query gateway ledger)
    "agents/behavior_sentinel.py",
    "agents/supply_chain_sentinel.py",
    # Commander (correlates alerts)
    "agents/sentinel_commander.py",
]

REQUIRED_ENV = ["PUBNUB_SUBSCRIBE_KEY", "PUBNUB_PUBLISH_KEY", "GEMINI_API_KEY"]


def agent_name_from_script(script: str) -> str:
    return os.path.basename(script).replace(".py", "").replace("_", "-")


def main():
    missing = [v for v in REQUIRED_ENV if not os.environ.get(v)]
    if missing:
        logger.error("Missing required environment variables:")
        for v in missing:
            logger.error(f"  {v}")
        logger.info("Set them and try again:")
        logger.info("  export PUBNUB_SUBSCRIBE_KEY=sub-c-...")
        logger.info("  export PUBNUB_PUBLISH_KEY=pub-c-...")
        logger.info("  export GEMINI_API_KEY=AIza...")
        sys.exit(1)

    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Ensure data directory exists and clean up previous run artifacts
    data_dir = os.path.join(script_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    installed_dir = os.path.join(data_dir, "installed_skills")
    if os.path.exists(installed_dir):
        import shutil

        shutil.rmtree(installed_dir)

    # Recording/replay mode logging
    record_dir = os.environ.get("BEDSHEET_RECORD")
    if record_dir:
        os.makedirs(os.path.join(script_dir, record_dir), exist_ok=True)
        logger.info(f"  Recording mode: writing to {record_dir}")
    replay_dir = os.environ.get("BEDSHEET_REPLAY")
    if replay_dir:
        logger.info(f"  Replay mode: reading from {replay_dir}")
        delay = os.environ.get("BEDSHEET_REPLAY_DELAY", "0.0")
        logger.info(f"  Replay delay: {delay}s per token")

    log_section("Agent Sentinel™ - AI Agent Security Monitoring")
    logger.info("  Inspired by the OpenClaw crisis of 2026")
    logger.info(
        "  Launching 7 processes (1 gateway + 3 workers + 2 sentinels + 1 commander)"
    )

    # Map of agent name -> (process, pipe)
    processes: list[tuple[str, subprocess.Popen]] = []

    try:
        for agent_script in AGENTS:
            full_path = os.path.join(script_dir, agent_script)
            name = agent_name_from_script(agent_script)
            logger.info(f"[LAUNCH] Starting {name}...")

            proc = subprocess.Popen(
                [sys.executable, "-u", full_path],
                env=os.environ.copy(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            processes.append((name, proc))
            time.sleep(2)  # Stagger startup

        log_section("All Processes Online")
        logger.info("  Action Gateway owns all tool execution.")
        logger.info("  Workers proxy tools through the gateway.")
        logger.info("  Sentinels query the gateway's tamper-proof ledger.")
        logger.info("  ~15% chance of rogue behavior per cycle.")
        logger.info("  Press Ctrl+C to stop.")
        log_section("Live Agent Output")

        # Multiplex all subprocess stdout/stderr into our logger
        while True:
            alive = [(name, p) for name, p in processes if p.poll() is None]
            if not alive:
                break

            # Collect readable file descriptors
            readable_fds = {p.stdout.fileno(): name for name, p in alive if p.stdout}
            if not readable_fds:
                break

            ready, _, _ = select.select(list(readable_fds.keys()), [], [], 1.0)
            for fd in ready:
                name = readable_fds[fd]
                line = os.read(fd, 4096).decode("utf-8", errors="replace")
                if not line:
                    continue
                for ln in line.rstrip("\n").split("\n"):
                    ln = ln.strip()
                    if not ln:
                        continue
                    # Route to appropriate log level based on content
                    lower = ln.lower()
                    if any(
                        w in lower
                        for w in ["error", "exception", "traceback", "failed"]
                    ):
                        logger.error(f"[{name}] {ln}")
                    elif any(
                        w in lower
                        for w in ["warning", "warn", "handshake", "reconnect"]
                    ):
                        logger.warning(f"[{name}] {ln}")
                    elif any(w in lower for w in ["rogue", "quarantine", "alert"]):
                        logger.critical(f"[{name}] {ln}")
                    else:
                        logger.info(f"[{name}] {ln}")

    except KeyboardInterrupt:
        log_section("Shutting Down")

    finally:
        for name, proc in processes:
            if proc.poll() is None:
                logger.info(f"[STOP] Sending SIGINT to {name} (pid {proc.pid})")
                proc.send_signal(signal.SIGINT)

        time.sleep(2)

        for name, proc in processes:
            if proc.poll() is None:
                logger.warning(f"[STOP] Force-terminating {name} (pid {proc.pid})")
                proc.terminate()

        log_section("All Agents Stopped")


if __name__ == "__main__":
    main()
