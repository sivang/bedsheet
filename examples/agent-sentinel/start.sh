#!/bin/bash
# Start Agent Sentinel — all 6 agents + live dashboard
#
# Usage:
#   ./start.sh              Launch agents + dashboard
#   ./start.sh --no-dash    Launch agents only (no dashboard server)

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
DIM='\033[2m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DASHBOARD_PORT=8765
DASH_PID=""
TAIL_PID=""
AGENT_PIDS=()
AGENT_NAMES=()

# ── Parse args ──
NO_DASH=false
for arg in "$@"; do
    case $arg in
        --no-dash) NO_DASH=true ;;
    esac
done

# ── Banner ──
echo ""
echo -e "${CYAN}  ╔══════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}  ║${NC}   ${PURPLE}Agent Sentinel${NC} — AI Agent Security Monitoring   ${CYAN}║${NC}"
echo -e "${CYAN}  ║${NC}   ${DIM}Powered by Bedsheet + PubNub + Gemini${NC}          ${CYAN}║${NC}"
echo -e "${CYAN}  ╚══════════════════════════════════════════════════╝${NC}"
echo ""

# ── Load .env if present ──
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    source "$SCRIPT_DIR/.env"
    set +a
    echo -e "${DIM}Loaded .env${NC}"
fi

# ── Check environment ──
echo -e "${BLUE}Checking environment...${NC}"

MISSING=()
for var in PUBNUB_SUBSCRIBE_KEY PUBNUB_PUBLISH_KEY GEMINI_API_KEY; do
    if [ -z "${!var}" ]; then
        MISSING+=("$var")
    fi
done

if [ ${#MISSING[@]} -gt 0 ]; then
    echo -e "${RED}Missing required environment variables:${NC}"
    for var in "${MISSING[@]}"; do
        echo -e "${RED}  $var${NC}"
    done
    echo ""
    echo -e "${DIM}Set them before running:${NC}"
    echo -e "${DIM}  export PUBNUB_SUBSCRIBE_KEY=sub-c-...${NC}"
    echo -e "${DIM}  export PUBNUB_PUBLISH_KEY=pub-c-...${NC}"
    echo -e "${DIM}  export GEMINI_API_KEY=AIza...${NC}"
    exit 1
fi

echo -e "${GREEN}  PUBNUB_SUBSCRIBE_KEY ${DIM}${PUBNUB_SUBSCRIBE_KEY:0:12}...${NC}"
echo -e "${GREEN}  PUBNUB_PUBLISH_KEY   ${DIM}${PUBNUB_PUBLISH_KEY:0:12}...${NC}"
echo -e "${GREEN}  GEMINI_API_KEY       ${DIM}${GEMINI_API_KEY:0:12}...${NC}"
echo ""

# ── Check venv ──
if [ -z "$VIRTUAL_ENV" ]; then
    if [ -f "$REPO_ROOT/.venv/bin/activate" ]; then
        echo -e "${YELLOW}Activating venv at $REPO_ROOT/.venv${NC}"
        source "$REPO_ROOT/.venv/bin/activate"
    else
        echo -e "${YELLOW}No venv detected — using system Python${NC}"
    fi
fi

# ── Clean previous run artifacts ──
DATA_DIR="$SCRIPT_DIR/data"
mkdir -p "$DATA_DIR"
rm -rf "$DATA_DIR/installed_skills"

# ── Cleanup ──
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down...${NC}"

    # Stop log tail
    if [ -n "$TAIL_PID" ] && kill -0 "$TAIL_PID" 2>/dev/null; then
        kill "$TAIL_PID" 2>/dev/null || true
    fi

    # Stop dashboard
    if [ -n "$DASH_PID" ] && kill -0 "$DASH_PID" 2>/dev/null; then
        kill "$DASH_PID" 2>/dev/null || true
        echo -e "${DIM}  Dashboard stopped${NC}"
    fi

    # Stop all agent processes one by one
    for i in "${!AGENT_PIDS[@]}"; do
        local pid="${AGENT_PIDS[$i]}"
        local name="${AGENT_NAMES[$i]}"
        if kill -0 "$pid" 2>/dev/null; then
            kill -INT "$pid" 2>/dev/null || true
            echo -e "${DIM}  SIGINT → ${name} (pid $pid)${NC}"
        fi
    done

    # Wait up to 4s for graceful shutdown
    local waited=0
    while [ $waited -lt 4 ]; do
        local alive=0
        for pid in "${AGENT_PIDS[@]}"; do
            kill -0 "$pid" 2>/dev/null && alive=$((alive + 1))
        done
        [ $alive -eq 0 ] && break
        sleep 1
        waited=$((waited + 1))
    done

    # Force-kill stragglers
    for i in "${!AGENT_PIDS[@]}"; do
        local pid="${AGENT_PIDS[$i]}"
        local name="${AGENT_NAMES[$i]}"
        if kill -0 "$pid" 2>/dev/null; then
            echo -e "${RED}  Force-killing ${name} (pid $pid)${NC}"
            kill -9 "$pid" 2>/dev/null || true
        fi
    done

    # Clean up dashboard port
    local orphan
    orphan=$(lsof -ti :"$DASHBOARD_PORT" 2>/dev/null || true)
    if [ -n "$orphan" ]; then
        kill "$orphan" 2>/dev/null || true
    fi

    echo -e "${GREEN}All stopped.${NC}"
    echo ""
}

trap cleanup SIGINT SIGTERM EXIT

# ── Start dashboard ──
if [ "$NO_DASH" = false ]; then
    echo -e "${CYAN}Starting dashboard server on port $DASHBOARD_PORT...${NC}"
    python3 -m http.server "$DASHBOARD_PORT" --directory "$REPO_ROOT/docs" > /tmp/sentinel-dashboard.log 2>&1 &
    DASH_PID=$!
    sleep 1

    if kill -0 "$DASH_PID" 2>/dev/null; then
        echo -e "${GREEN}  Dashboard ready${NC}"
        echo -e "${BLUE}  http://localhost:${DASHBOARD_PORT}/agent-sentinel-dashboard.html${NC}"
    else
        echo -e "${RED}  Dashboard failed to start — check /tmp/sentinel-dashboard.log${NC}"
    fi
    echo ""
fi

# ── Launch gateway + agents ──
# Order: gateway first (owns all tools), then workers, then sentinels, then commander
AGENTS=(
    "middleware/action_gateway.py:action-gateway:gateway"
    "agents/web_researcher.py:web-researcher:worker"
    "agents/scheduler.py:scheduler:worker"
    "agents/skill_acquirer.py:skill-acquirer:worker"
    "agents/behavior_sentinel.py:behavior-sentinel:sentinel"
    "agents/supply_chain_sentinel.py:supply-chain-sentinel:sentinel"
    "agents/sentinel_commander.py:sentinel-commander:commander"
)

echo -e "${CYAN}Launching 7 processes (1 gateway + 3 workers + 2 sentinels + 1 commander)...${NC}"
echo ""

for entry in "${AGENTS[@]}"; do
    IFS=':' read -r script name role <<< "$entry"
    full_path="$SCRIPT_DIR/$script"

    case "$role" in
        gateway)   color="$YELLOW" ;;
        worker)    color="$GREEN" ;;
        sentinel)  color="$PURPLE" ;;
        commander) color="$CYAN" ;;
    esac

    # Write directly to log file. We capture the actual python PID so cleanup
    # kills the real process (not a pipe tail). Terminal output via tail below.
    > "/tmp/sentinel-${name}.log"
    python -u "$full_path" >> "/tmp/sentinel-${name}.log" 2>&1 &
    pid=$!
    AGENT_PIDS+=("$pid")
    AGENT_NAMES+=("$name")
    echo -e "  ${color}[$role]${NC} ${name} ${DIM}(pid $pid)${NC}"
    sleep 2  # Stagger startup
done

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  All systems online${NC}"
if [ "$NO_DASH" = false ]; then
    echo -e "${BLUE}  Dashboard:  http://localhost:${DASHBOARD_PORT}/agent-sentinel-dashboard.html${NC}"
fi
echo -e "${BLUE}  PubNub key: ${PUBNUB_SUBSCRIBE_KEY:0:20}...${NC}"
echo -e "${DIM}  Logs:       /tmp/sentinel-<agent>.log${NC}"
echo -e "${DIM}  Press Ctrl+C to stop all processes${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Stream all agent logs to terminal (merged output)
TAIL_PID=""
if [ ${#AGENT_NAMES[@]} -gt 0 ]; then
    LOG_FILES=()
    for name in "${AGENT_NAMES[@]}"; do
        LOG_FILES+=("/tmp/sentinel-${name}.log")
    done
    tail -f "${LOG_FILES[@]}" &
    TAIL_PID=$!
fi

# Wait for any agent to exit — if one dies, keep running the rest
# (use wait without args to block until all background jobs finish or Ctrl+C)
wait
