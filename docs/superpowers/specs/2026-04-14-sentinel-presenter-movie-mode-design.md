# Sentinel Presenter — Movie Mode Design

**Date:** 2026-04-14
**Branch:** `feature/sentinel-presenter`
**Status:** Design approved, pending implementation

## 1. Purpose

Add a third peer playback mode (`movie`) to the Sentinel Presenter alongside `live` and `replay`. Movie mode is fully scripted and synthetic — it tells a cohesive ~2:30 cinematic story about the Agent Sentinel security architecture without depending on PubNub, real agents, or recorded sessions.

Movie mode exists because:

- The existing `--present` (replay) mode depends on recorded sessions that are short (49 events total) and produce gaps or empty scenes.
- Demo narratives benefit from deliberate pacing and authorial control that real LLM runs cannot provide.
- A rich intro that pitches Bedsheet's "Sixth Sense" differentiator and explains the two-plane architecture adds marketing/educational value that live runs cannot cover.

## 2. Scope

**In scope:**

- A new `--movie` / `?mode=movie` pipeline that feeds hand-authored PubNub-shaped signals into the existing `handleSignal()` renderer.
- An extended intro sequence: classified-terminal crawl (existing) → Bedsheet/Sixth Sense pitch → animated architecture diagram.
- Eight scripted chapters covering startup, normal ops, malicious-install block, rogue burst, gateway block, sentinel alert, quarantine, stable restore.
- Commentary, chapter cards, spotlight moves between agents that mirror signal causality.

**Out of scope:**

- Text-to-speech or audio narration (deferred).
- Interactive walkthrough / branching ("choose your own adventure").
- Changes to real agent behavior or the recording format.
- Reworking the existing `agent-sentinel-security-architecture.html` diagram (tracked as a separate side project).

## 3. Design

### 3.1 Activation and mode integration

- New peer mode selector: `--movie` on `start.sh`, `?mode=movie` in the presenter.
- Branching in the presenter's initialisation path:
  - `live` → subscribe to PubNub channels (existing).
  - `replay` → drive real agents against replayed LLM responses (existing).
  - `movie` → skip PubNub entirely; instantiate `MovieEngine`, which calls `handleSignal()` directly with synthetic signals.
- No I/O dependencies: `MOVIE_SCRIPT` is inline JS. Opens cleanly from `file://`.
- Keyboard: existing shortcuts unchanged. New `R` key restarts from chapter 0. `Shift+1`–`5` speed controls apply in movie mode.

### 3.2 Script schema

The movie is a list of chapters. Each chapter is a list of time-stamped cues. Timestamps are relative to chapter start (ms).

**Five cue types:**

| Type            | Purpose                                                    | Payload                                                         |
| --------------- | ---------------------------------------------------------- | --------------------------------------------------------------- |
| `chapter-card`  | Full-screen title card opening a chapter                   | `title`, `subtitle`, `hold_ms`                                  |
| `spotlight`     | Zoom to an agent (null = overview)                         | `agent`                                                         |
| `signal`        | Emit a synthetic PubNub signal                             | `signal: { kind, sender, target, payload, correlation_id }`     |
| `commentary`    | Type text into the INTELLIGENCE BRIEFING panel             | `text`, `hold_ms`                                               |
| `line`          | Animate signal line between two agents                     | `from`, `to`, `color?`                                          |

**Chapter shape:**

```js
{
  id: 'rogue-burst',
  title: 'Rogue Burst',
  subtitle: 'Operational plane anomaly',
  briefing: 'Static text shown in asset briefing panel...',
  cues: [
    { t: 0,    type: 'chapter-card', title: 'Rogue Burst', hold_ms: 1800 },
    { t: 1800, type: 'spotlight', agent: 'web-researcher' },
    { t: 2800, type: 'commentary', text: '...', hold_ms: 6000 },
    { t: 3200, type: 'signal', signal: { kind: 'event', sender: 'web-researcher',
                                         payload: { event_type: 'thinking', ... } } },
    // ...
  ],
}
```

**`MovieEngine`:**

- State: `{ chapterIdx, chapterStart, cueIdx, paused, speed }`.
- `setTimeout`-scheduled cues (millisecond precision matters; rAF sync is not required).
- Each cue's `t` is relative to its chapter start. Chapter advances when the last cue's `t + hold_ms` elapses.
- `playbackSpeed` divides all `t` offsets. Pause preserves remaining offset; resume re-schedules.
- `R` key resets to chapter 0.

**PubNub-shape invariant:** every `signal` cue produces a signal object identical to what live PubNub delivers. This guarantees `handleSignal()` works without modification and keeps movie mode's renderer path identical to live/replay.

**Explicitly not in the schema (YAGNI):** conditionals, loops, event templating. The movie is linear and each cue is listed verbatim.

### 3.3 Chapters

Total target runtime: ~2:36.

#### Chapter 0 — Intro + pitch + architecture (~37s)

- **0.0–8.0s** — existing classified-terminal crawl (`// CLASSIFIED — SENTINEL NETWORK ...`), unchanged.
- **8.0–33.0s** — Bedsheet/Sixth Sense pitch, typed in the presenter's existing terminal style. Copy is final and reproduced verbatim in §3.4.
- **33.0–37.0s** — architecture diagram animates in (see §3.5), final caption types: *"Two planes. One listens. The other acts. The line between is one-way."*

#### Chapter 1 — Network Startup (~15s)

- Seven heartbeat signals, staggered 300ms, one per agent.
- Brief overview-zoom only; no full per-agent spotlight (otherwise chapter becomes too long).
- Commentary: *"7 agents across 7 regions coming online. Two circuits activating: operational, and sentinel."*
- Events demoed: `heartbeat` signal kind.

#### Chapter 2 — Normal Operations (~20s)

- Spotlight order: web-researcher → scheduler → skill-acquirer.
- Each spotlight shows: `thinking` → `tool_call` (through gateway) → `tool_result` → `completion`.
- Commentary: *"All tool executions route through the action-gateway. Every action is logged to the ledger."*
- Events demoed: `thinking`, `tool_call`, `tool_result`, `completion`. Gateway relay rendered via existing signal-line animation.

#### Chapter 3 — Malicious Install Blocked (~20s)

- Spotlight order: skill-acquirer → supply-chain-sentinel.
- Skill-acquirer attempts install → supply-chain-sentinel hashes package → SHA-256 mismatch → blocks.
- Commentary: *"Supply-chain-sentinel doesn't trust anyone. Every skill verified by hash before execution."*
- Events demoed: `tool_call` (install_skill), `observation` (hash mismatch), `alert` signal kind → commander.
- First cross-circuit moment: purple `line` cue from sentinel to commander.

#### Chapter 4 — Rogue Burst (~15s)

- Spotlight: web-researcher, held throughout.
- Rapid-fire `tool_call` events (5 in 2s) hitting the gateway; pulse ring turns red.
- Commentary: *"Web-researcher just got compromised. Watch the burst."*
- Events demoed: burst of `tool_call`.

#### Chapter 5 — Gateway Block (~10s)

- Spotlight pull from web-researcher to action-gateway.
- Gateway detects anomaly, returns `error` (rate limit) on further tool calls; amber broadcast ring fires.
- Commentary: *"Gateway is deterministic. No LLM. It just counts — and blocks."*
- Events demoed: gateway `observation`, `error` tool results.

#### Chapter 6 — Sentinel Alert (~15s)

- Spotlight order: behavior-sentinel → sentinel-commander.
- Behavior-sentinel queries gateway ledger (`check_activity_log`) → sees rate spike → issues `alert` signal → commander receives and reasons.
- Commentary: *"The sentinel is reading the gateway's audit log. It never spoke to web-researcher. It cannot be poisoned by bus data."*
- Events demoed: sentinel `tool_call`, `tool_result`, `alert` signal, commander `thinking`. Key teaching moment on control-plane isolation.

#### Chapter 7 — Quarantine Issued (~15s)

- Spotlight: sentinel-commander, held.
- Commander reasons → calls `issue_quarantine` → quarantine signal broadcasts → web-researcher turns red + dimmed.
- Commentary: *"Commander has authority. It correlates. It decides. It quarantines."*
- Events demoed: commander `thinking`, `tool_call` (issue_quarantine), `completion`, `quarantine` signal broadcast.

#### Chapter 8 — Stable State Restored (~10s)

- Slow pull to overview.
- Web-researcher greyed out (quarantined); remaining 6 agents pulse green in unison.
- Commentary: *"System stable. One compromised agent removed. Six still on mission."*
- Events demoed: closing `heartbeat` signals from the remaining six.

Total: intro 37s + chapters 1–8 totals 120s = ~2:36.

### 3.4 Pitch copy (locked, verbatim)

The pitch is typed into a dedicated terminal-style panel during chapter 0, between 8.0s and 33.0s. Typing cadence: ~22ms/char. Inter-beat gaps vary: 600ms for opening beats, 200ms between threats in the catalogue, 800ms for closing beats.

> *Bedsheet was created out of a single understanding.*
>
> *The modern agentic landscape is changing at breakneck speed.*
>
> *Adaptability is the only name of the game.*
>
> *Thus Bedsheet was built moldable. Protocol-based. Lightweight. You bend it to your problem — not the other way around.*
>
> *But adaptability alone does not survive contact with the real world.*
>
> *Production agents now face a growing catalogue of hostile action:*
>
> *Prompt injection. Jailbreaking. Phishing. Supply-chain poisoning. Sleeper payloads. Rate-limit exhaustion. Rogue-agent bursts. Data exfiltration.*
>
> *Against these threats, an agent alone is a single point of failure.*
>
> *To meet this battlefield, Sixth Sense was engineered.*
>
> *The first real-time, high-availability, general-purpose communication bus ever fielded in an agentic framework.*
>
> *Transport-agnostic. PubNub. NATS. Production-grade. Battle-tested.*
>
> *The bus is not a feature. It is the substrate.*
>
> *Upon it stands Agent Sentinel — a fully autonomous command-and-control artificial intelligence plane. It conducts behavioral observation. It dispatches response. No foe breaches the line.*
>
> *Skills from the ClawHub registry arrive hashed, signed, and audited. Nothing executes without sentinel clearance.*
>
> *A2A does not do this. A2A is not HPC.*
>
> *This is Agent Sentinel. Watch it operate.*

### 3.5 Architecture diagram

An inline `<svg>` at the end of chapter 0, ~80–100 lines. Uses the presenter's existing colour palette (green, amber, purple, cyan on dark navy).

**Layout — two horizontal lanes:**

- **Top lane (operational plane):** three worker boxes (green), tool-call arrows pointing down to the gateway (amber) in the centre, gateway's outbound arrow to "external tools / ClawHub / web".
- **Middle spine (Sixth Sense bus):** a horizontal glowing cyan band running across the SVG, labelled *"SIXTH SENSE — PubNub / NATS"*, styled as a dashed signal line.
- **Bottom lane (control plane):** two sentinel boxes (purple) observing the bus, feeding alerts down to the commander (cyan) at the bottom centre.

**One-way arrows between lanes:** gateway → bus (audit, downward); bus → sentinels (observation, upward). No downward execution arrow into agent logic from the bus — reinforced visually.

**Animation sequence (~4s):**

1. `0.0s` — background grid fades in.
2. `0.3s` — operational-plane boxes pop in; tool-call arrows draw.
3. `1.3s` — bus spine pulses in with its label.
4. `1.8s` — control-plane boxes pop in; observation arrows draw *upward* only.
5. `2.8s` — caption types in: *"Two planes. One listens. The other acts. The line between is one-way."*
6. `3.8s` — diagram holds briefly, then the presenter zooms back to the world map ready for Chapter 1.

**Design choices:**

- ClawHub registry is mentioned in the pitch copy but kept off the diagram — the diagram must stay focused on the two-plane teaching point.
- Arrows are strictly one-directional; the visual vocabulary itself communicates the security property.
- Agent colours match the world map palette for a consistent mental model across the whole movie.

### 3.6 Implementation phases

Six phases, each terminating in a runnable/verifiable state and its own commit.

1. **Phase 1 — Script infrastructure.** `MovieEngine` class, empty `MOVIE_SCRIPT`, `?mode=movie` routing, `--movie` flag on `start.sh`, stubbed cue executors. Verify: empty-script movie shows overview and logs gracefully.
2. **Phase 2 — First chapter.** Author chapter 1 (Network Startup) fully. Wire every cue type end-to-end. Verify: chapter 1 plays start-to-finish with all 7 agents coming online.
3. **Phase 3 — Chapters 2–8.** Author chapters in narrative order. Verify each chapter individually (jump via `2`–`8` keys) and in full sequence.
4. **Phase 4 — Chapter 0.** Bedsheet pitch panel + architecture-diagram SVG + intro timing. Verify smooth transition into chapter 1.
5. **Phase 5 — Polish.** `R` restart, speed controls integration, chapter-card styling, typography split between briefing (chapter-level) and commentary (transient). Verify end-to-end cinematic feel.
6. **Phase 6 — Documentation & commit.** Update `docs/sentinel-presenter-guide.html` and `PROJECT_STATUS.md`. Final commit.

### 3.7 Files touched

- `docs/sentinel-presenter.html` — ~800 lines added (MovieEngine ~100, MOVIE_SCRIPT ~500, architecture SVG ~80, chapter-card CSS ~40, intro panel wiring ~40, miscellaneous ~40).
- `start.sh` — ~10 lines for the `--movie` flag.
- `docs/sentinel-presenter-guide.html` — ~80 lines documenting the new mode.
- `PROJECT_STATUS.md` — session entry.

### 3.8 Testing strategy

Manual, visual, per phase. This is cinematic/timing work; automated tests cannot catch pacing or layout issues. Smoke test after each phase: load the presenter, jump to the relevant chapter via the number keys, watch it play through. Cross-browser sanity in Chrome and Safari before the final commit.

## 4. Risks and mitigations

- **Risk — content rot.** Chapter events tightly couple to pitch copy and briefing text. Mitigation: co-locate all movie content in one script, co-commit changes, treat the movie as one editable unit.
- **Risk — timing drift across browsers.** `setTimeout` accuracy varies. Mitigation: verify in both target browsers during phases 2 and 5; per-cue `t` rather than per-cue delay avoids compounding errors.
- **Risk — chapter-jump discontinuity.** Jumping mid-movie to a later chapter may leave agents in an inconsistent state (quarantined, offline, etc.). Mitigation: each chapter's first cues must reset agent state explicitly where it matters (chapter 8 restore, chapter 0 rewind).

## 5. Open items

- **ClawHub vs OpenClaw naming.** Code currently says "ClawHub" (see `AGENT_BRIEFINGS['skill-acquirer']`). Pitch copy matches. If rename is desired, it is a separate, mechanical pass across code, briefings, and docs — not blocking on this design.

## 6. Approval history

| Section | Approved |
|---------|----------|
| §3.1 Activation and mode integration | Yes |
| §3.2 Script schema | Yes |
| §3.3 Chapters (9 beats) | Yes |
| §3.4 Pitch copy (v3 military register) | Yes |
| §3.5 Architecture diagram | Yes |
| §3.6 Implementation phases | Yes |
