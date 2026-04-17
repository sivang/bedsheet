#!/bin/bash
# Start Agent Sentinel™ — all 6 agents + live dashboard
#
# Usage:
#   ./start.sh                Launch agents + dashboard (live mode)
#   ./start.sh --record       Record all LLM + tool interactions to recordings/
#   ./start.sh --replay       Replay from recordings/ (no API keys needed)
#   ./start.sh --replay 0.1   Replay with delay between tokens (seconds)
#   ./start.sh --no-dash      Launch without dashboard server
#   ./start.sh --quiet        Suppress LLM event output (only show key events)
#   ./start.sh --present      Cinematic presenter mode (implies --replay 0.3)
#   ./start.sh --present --cinematic  Start in cinematic mode (no UI chrome)
#   ./start.sh --movie        Fully-scripted ~2:44 movie (no agents, no recordings)
#   ./start.sh --help         Show this help and exit
#
# Flags can be combined: ./start.sh --record --no-dash --quiet

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

# ── Help ──
show_help() {
    local me
    me="$(basename "$0")"
    echo ""
    echo -e "  ${CYAN}Agent Sentinel${NC} — launcher"
    echo ""
    echo -e "  ${DIM}Usage:${NC}"
    echo -e "    ${me} [flag ...]"
    echo ""
    echo -e "  ${DIM}Modes (pick one; default is live PubNub):${NC}"
    echo -e "    ${GREEN}--record${NC}               Run live, save all LLM + tool calls to recordings/"
    echo -e "    ${GREEN}--replay${NC} [delay]       Replay from recordings/ (no API keys needed). Optional"
    echo -e "                           per-token delay in seconds (e.g. ${DIM}--replay 0.1${NC})."
    echo -e "    ${GREEN}--present${NC}              Cinematic presenter mode (implies ${DIM}--replay 0.3${NC})."
    echo -e "    ${GREEN}--movie${NC}                Fully-scripted demo — no agents, no PubNub, no recordings."
    echo -e "                           Director mode by default: press ${DIM}N${NC} to advance chapters, ${DIM}E${NC} to"
    echo -e "                           drag-reposition panels, ${DIM}X${NC} to export positions. See the guide."
    echo ""
    echo -e "  ${DIM}Modifiers:${NC}"
    echo -e "    ${GREEN}--no-dash${NC}              Launch without the dashboard HTTP server."
    echo -e "    ${GREEN}--quiet${NC}                Suppress per-event LLM output."
    echo -e "    ${GREEN}--cinematic${NC}            With ${DIM}--present${NC}: start in cinematic mode (no UI chrome)."
    echo ""
    echo -e "  ${DIM}Misc:${NC}"
    echo -e "    ${GREEN}--help${NC}, ${GREEN}-h${NC}             Show this help and exit."
    echo ""
    echo -e "  ${DIM}Examples:${NC}"
    echo -e "    ${me}                      ${DIM}# Live PubNub mode${NC}"
    echo -e "    ${me} --replay 0.1         ${DIM}# Fast replay from recordings/${NC}"
    echo -e "    ${me} --present            ${DIM}# Cinematic replay for demos${NC}"
    echo -e "    ${me} --movie              ${DIM}# Synthetic scripted demo${NC}"
    echo -e "    ${me} --record --quiet     ${DIM}# Capture a session, low verbosity${NC}"
    echo ""
    echo -e "  ${DIM}Dashboard URL (when enabled):${NC}"
    echo -e "    http://localhost:${DASHBOARD_PORT}/"
    echo ""
}

# ── Parse args ──
NO_DASH=false
RECORD=false
REPLAY=false
REPLAY_DELAY="0.0"
QUIET=false
PRESENT=false
CINEMATIC=false
MOVIE=false
while [ $# -gt 0 ]; do
    case $1 in
        --no-dash) NO_DASH=true ;;
        --quiet)   QUIET=true ;;
        --record)  RECORD=true ;;
        --replay)
            REPLAY=true
            # Check if next arg is a number (delay value)
            if [ -n "${2:-}" ] && [[ "$2" =~ ^[0-9]*\.?[0-9]+$ ]]; then
                REPLAY_DELAY="$2"
                shift
            fi
            ;;
        --present)
            PRESENT=true
            # Implies replay mode with default 0.3s delay (if not already set)
            if [ "$REPLAY" = false ]; then
                REPLAY=true
                REPLAY_DELAY="0.3"
            fi
            ;;
        --cinematic) CINEMATIC=true ;;
        --movie)   MOVIE=true ;;
        --help|-h) show_help; exit 0 ;;
    esac
    shift
done

# Movie mode is fully synthetic — no agents, no PubNub, no recordings.
# Just the HTTP server serving the presenter HTML. Keep the dashboard on;
# do NOT turn REPLAY/PRESENT on (those launch agents — wasted in movie mode).
if [ "$MOVIE" = true ]; then
    NO_DASH=false
fi

if [ "$RECORD" = true ] && [ "$REPLAY" = true ]; then
    echo -e "${RED}Cannot use --record and --replay together${NC}"
    exit 1
fi

# ── Banner ──
echo ""
echo -e "${CYAN}  ╔══════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}  ║${NC}   ${PURPLE}Agent Sentinel™${NC} — AI Agent Security Monitoring  ${CYAN}║${NC}"
echo -e "${CYAN}  ║${NC}   ${DIM}Powered by Bedsheet + PubNub + Gemini${NC}          ${CYAN}║${NC}"
echo -e "${CYAN}  ╚══════════════════════════════════════════════════╝${NC}"
if [ "$MOVIE" = true ]; then
    echo -e "   ${CYAN}▶ MOVIE MODE${NC} — fully-scripted demo (no agents, no PubNub)"
elif [ "$PRESENT" = true ]; then
    echo -e "   ${CYAN}▶ PRESENTER MODE${NC} — cinematic demo playback"
elif [ "$RECORD" = true ]; then
    echo -e "   ${YELLOW}● RECORDING MODE${NC} — saving to recordings/"
elif [ "$REPLAY" = true ]; then
    echo -e "   ${GREEN}▶ REPLAY MODE${NC} — reading from recordings/ (delay: ${REPLAY_DELAY}s)"
fi
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

if [ "$REPLAY" = true ]; then
    # Replay mode — no API keys needed
    echo -e "${GREEN}  Replay mode — no API keys required${NC}"
    echo ""
else
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
fi

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

    # Clean up generated dashboard config
    rm -f "$REPO_ROOT/docs/sentinel-config.js"

    echo -e "${GREEN}All stopped.${NC}"
    echo ""
}

trap cleanup SIGINT SIGTERM EXIT

# ── Start dashboard ──
if [ "$NO_DASH" = false ]; then
    # Write config for dashboard auto-connect
    if [ -n "${PUBNUB_SUBSCRIBE_KEY:-}" ]; then
        echo "window.SENTINEL_CONFIG = { subscribeKey: '${PUBNUB_SUBSCRIBE_KEY}' };" > "$REPO_ROOT/docs/sentinel-config.js"
    fi

    echo -e "${CYAN}Starting dashboard server on port $DASHBOARD_PORT...${NC}"
    python3 -m http.server "$DASHBOARD_PORT" --directory "$REPO_ROOT/docs" > /tmp/sentinel-dashboard.log 2>&1 &
    DASH_PID=$!
    sleep 1

    # Choose presenter or dashboard page
    if [ "$MOVIE" = true ]; then
        DASH_PAGE="sentinel-presenter.html?mode=movie"
        if [ "$CINEMATIC" = true ]; then
            DASH_PAGE="sentinel-presenter.html?mode=movie#cinematic"
        fi
        DASH_LABEL="Movie"
    elif [ "$PRESENT" = true ]; then
        DASH_PAGE="sentinel-presenter.html"
        if [ "$CINEMATIC" = true ]; then
            DASH_PAGE="sentinel-presenter.html#cinematic"
        fi
        DASH_LABEL="Presenter"
    else
        DASH_PAGE="agent-sentinel-dashboard.html"
        DASH_LABEL="Dashboard"
    fi

    if kill -0 "$DASH_PID" 2>/dev/null; then
        echo -e "${GREEN}  ${DASH_LABEL} ready${NC}"
        echo -e "${BLUE}  http://localhost:${DASHBOARD_PORT}/${DASH_PAGE}${NC}"
    else
        echo -e "${RED}  ${DASH_LABEL} failed to start — check /tmp/sentinel-dashboard.log${NC}"
    fi
    echo ""
fi

# ── Launch gateway + agents ──
# (Skipped entirely in movie mode — movie is fully synthetic, no agents needed.)
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

if [ "$MOVIE" = true ]; then
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}  Movie ready${NC}"
    echo -e "${CYAN}  Mode:      MOVIE (synthetic — no agents, no PubNub)${NC}"
    echo -e "${BLUE}  Movie:     http://localhost:${DASHBOARD_PORT}/${DASH_PAGE}${NC}"
    echo -e "${DIM}  Dismiss the intro crawl (Space/Enter) to start the movie.${NC}"
    echo -e "${DIM}  Press Ctrl+C to stop the HTTP server.${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    # Wait on the HTTP server (DASH_PID); Ctrl+C kills it and us.
    wait "$DASH_PID"
    exit 0
fi

# ── Set verbose/recording/replay env vars (inherited by child processes) ──
if [ "$QUIET" = false ]; then
    export BEDSHEET_VERBOSE=1
fi

if [ "$RECORD" = true ]; then
    RECORDING_DIR="$SCRIPT_DIR/recordings"
    mkdir -p "$RECORDING_DIR"
    export BEDSHEET_RECORD="$RECORDING_DIR"
fi

if [ "$REPLAY" = true ]; then
    RECORDING_DIR="$SCRIPT_DIR/recordings"
    if [ ! -d "$RECORDING_DIR" ] || [ -z "$(ls -A "$RECORDING_DIR"/*.jsonl 2>/dev/null)" ]; then
        echo -e "${RED}No recordings found in $RECORDING_DIR${NC}"
        echo -e "${DIM}Record first with: ./start.sh --record${NC}"
        exit 1
    fi
    export BEDSHEET_REPLAY="$RECORDING_DIR"
    export BEDSHEET_REPLAY_DELAY="$REPLAY_DELAY"
fi

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
if [ "$PRESENT" = true ]; then
    echo -e "${CYAN}  Mode:       PRESENTER (cinematic demo playback)${NC}"
elif [ "$RECORD" = true ]; then
    echo -e "${YELLOW}  Mode:       RECORDING to recordings/${NC}"
elif [ "$REPLAY" = true ]; then
    echo -e "${GREEN}  Mode:       REPLAY from recordings/ (delay: ${REPLAY_DELAY}s)${NC}"
fi
if [ "$NO_DASH" = false ]; then
    echo -e "${BLUE}  ${DASH_LABEL:-Dashboard}:  http://localhost:${DASHBOARD_PORT}/${DASH_PAGE:-agent-sentinel-dashboard.html}${NC}"
fi
if [ "$REPLAY" != true ]; then
    echo -e "${BLUE}  PubNub key: ${PUBNUB_SUBSCRIBE_KEY:0:20}...${NC}"
fi
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
