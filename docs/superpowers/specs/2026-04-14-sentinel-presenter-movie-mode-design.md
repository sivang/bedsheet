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
  - `movie` → skip PubNub entirely; instantiate `MovieEngine`. MovieEngine calls renderer primitives **directly** (see §3.1.1); it does **not** route through `handleSignal → eventBuffer → drainMapEvents`, because that path paces at 800ms and would coalesce rapid bursts. `handleSignal()` is still used for its LLM-event-card rendering side effect, but map effects are driven by explicit primitive calls per cue.
- No I/O dependencies: `MOVIE_SCRIPT` is inline JS. Opens cleanly from `file://`.
- **Mode is boot-time-immutable.** The selected mode (`live` | `replay` | `movie`) is resolved once at page load and never switches at runtime. This prevents coexistence of the wrapped-timer movie path and the unwrapped live/replay paths within the same session.
- Keyboard overrides in movie mode:
  - `1`–`9` rebinds from `jumpToScene` (agent scenes, used in replay) to **`jumpToChapter`** (chapter 1–8).
  - `Shift+1`–`5` keeps speed control.
  - `R` restarts from chapter 0 (cancels all pending timers, calls `resetPresenterVisuals()`, rewinds).
  - Space/arrows/F/C/T unchanged.
  - `detectChapter()` and `CHAPTER_COMMENTARY` (the replay-mode chapter-detection path) are bypassed in movie mode — every chapter card is driven by explicit `chapter-card` cues so no duplicated commentary.

#### 3.1.1 Renderer primitives required

Movie mode relies on a small set of renderer entry points, some existing, some new. Line numbers refer to `docs/sentinel-presenter.html` at HEAD of `feature/sentinel-presenter`.

| Primitive | Status | Purpose |
|---|---|---|
| `zoomToAgent(name, {durationMs?})` (line 1665) | **extend existing** — add optional duration override (current 0.8s via CSS transition on `.map-viewport`, line 150). Implementation: set `mapViewport.style.transitionDuration = durationMs + 'ms'` immediately before the transform assignment, and restore the empty string (`= ''`) once the `transitionend` event fires or after `durationMs + 100ms` fallback. | spotlight move |
| `zoomToOverview({durationMs?})` (line 1701) | **extend existing** — same override mechanic as `zoomToAgent`. Used by Ch 8's slow pull (3000ms). | overview move |
| `pulseNode(agent)` (line 1601) | existing | agent pulse |
| `animateSignalLine(from, to, color)` (line 1613) | existing | `line` cue |
| `animateBroadcast(agent)` (line 1629) | existing | gateway rate-block ring |
| `setAgentOnline(agent)` (line 1586) | existing | online state |
| Quarantine state | inline `classList.add('quarantined')` (see line 2355 for the existing pattern) | not a dedicated function; `driveMapEffectForSignal` applies the class directly for `kind: 'quarantine'` signals |
| `buildEventCard(signal)` (line 1913) | existing | constructs the `<div>` card for LLM events; movie mode's `signal` cue appends it to `#focusBody` directly (NOT via `handleMessage`, which has side effects we don't want — scene collection, `eventBuffer` push, `collecting` timer) |
| `showCommentary(text, holdMs)` | **new** | transient commentary panel |
| `showChapterCard(title, subtitle, holdMs)` | **new** | full-screen chapter card |
| `showPitch(lines, onComplete?)` / `hidePitch()` | **new** | typed Bedsheet pitch panel (Ch 0) |
| `showArchDiagram(caption, onComplete?)` / `hideArchDiagram()` | **new** | animated architecture diagram (Ch 0) |
| `resetPresenterVisuals()` | **new** | clears: `.quarantined`/`.focused`/`.dimmed`/`.online` classes, all `<line>` children of `#signalLines`, active `broadcast-ring` rings, `currentFocus`, `stats`, `onlineAgents` set, `agentScenes`/`agentOrder`/`presentedEvents` state, pending node-pulse classes |
| `driveMapEffectForSignal(signal)` | **new** | dispatches to `pulseNode`/`animateBroadcast`/`animateSignalLine` based on signal kind and payload, bypassing the 800ms `drainMapEvents` pacing |
| `MovieEngine.scheduleCue(cue)` | **new** | internal; wraps setTimeout with registered handle so `MovieEngine.cancelAll()` can tear them down on restart/pause |
| `MovieEngine.setSpeed(newSpeed)` | **new** | clears `pendingTimers`, recomputes remaining offsets under `newSpeed`, re-schedules |

**On entry integration:** the existing `dismissIntro()` handler (line 1424) currently calls `proceedToConnect()` at the end, which goes to PubNub. In movie mode, `dismissIntro()` must branch to `startMovieMode()` instead — the intro crawl still gates movie start (user-paced), which is the same UX as live/replay.

### 3.2 Script schema

The movie is a list of chapters. Each chapter is a list of time-stamped cues. Timestamps are relative to chapter start (ms).

**Ten cue types** — six core, four Chapter-0-only overlay cues:

| Type            | Purpose                                                    | Payload                                                         |
| --------------- | ---------------------------------------------------------- | --------------------------------------------------------------- |
| `chapter-card`  | Full-screen title card opening a chapter                   | `title`, `subtitle`, `hold_ms`                                  |
| `spotlight`     | Zoom to an agent (or overview)                             | `agent: 'name' \| null`, `duration_ms?` (default 800)          |
| `signal`        | Emit a synthetic signal: event card + map effect           | `signal: { kind, sender, target, payload, correlation_id }`    |
| `commentary`    | Type text into the commentary panel                        | `text`, `hold_ms`                                               |
| `line`          | Animate signal line between two agents                     | `from`, `to`, `color?` (hex or CSS var; default = sender role colour from `ROLE_COLORS`) |
| `reset`         | Clear visual state                                         | `scope: 'all'` (default; `'agents'` and `'lines'` **deferred** — not used by any Phase 2–3 chapter; `'all'` is sufficient for Ch 0–8) |
| `movie-pitch-start` | Show the pitch panel and begin typing Bedsheet copy    | (none; reads `PITCH_LINES` constant)                            |
| `movie-pitch-end`   | Hide the pitch panel                                   | (none)                                                          |
| `movie-arch-start`  | Reveal architecture diagram with draw-in animation + caption | (none; caption constant in implementation)              |
| `movie-arch-end`    | Hide architecture diagram                              | (none)                                                          |

**Why the four overlay cues are schema-level, not ad-hoc:** every timed visual effect in the movie must flow through `MovieEngine.scheduleCue()` so that pause, speed-change, restart, and chapter-jump all tear them down correctly. Calling `showPitch()` directly from chapter-0 bootstrap would bypass the timer registry and leak through mode transitions.

**`spotlight` semantics:**
- `agent: 'web-researcher'` → `zoomToAgent('web-researcher', {durationMs})`, sets `currentFocus`, applies `.focused`/`.dimmed` classes, invokes `positionBothOverlays` + `showBriefingOverlay`.
- `agent: null` → `zoomToOverview({durationMs})`, clears `currentFocus`, removes `.focused`/`.dimmed` from all nodes, hides focus + briefing overlays.
- `duration_ms` applies a CSS `transition-duration` override for that one move (Ch 8's "slow pull" uses 3000ms).

**`signal` semantics:**
- The signal object is PubNub-shaped so `handleSignal()` can render the LLM event card in the focus overlay.
- But the map-level visual effect is **additionally** driven by the engine calling the matching primitive directly (`pulseNode` / `animateBroadcast` / `animateSignalLine`) — not by `drainMapEvents`. This bypass is required so Chapter 4's 5-in-2s burst renders at burst rate instead of being paced to 800ms intervals.

**`line` semantics:**
- Resolves `color`: if present, used verbatim (hex or CSS var); if absent, looks up `ROLE_COLORS[AGENTS[from].role].hex`.
- Directly calls existing `animateSignalLine(from, to, resolvedColor)`.

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

- State: `{ chapterIdx, chapterStart, cueIdx, paused, speed, pendingTimers: Set<timerId> }`.
- `setTimeout`-scheduled cues via `scheduleCue()`, which registers each timer id in `pendingTimers` for tear-down.
- Each cue's `t` is relative to its chapter start. Chapter advances when the last cue's `t + hold_ms` elapses.
- **Pause:** records current elapsed position per pending cue, clears all `pendingTimers`, stops. Resume: re-schedules each pending cue with its remaining offset.
- **Speed change** (Shift+1–5): clears all `pendingTimers`, recomputes remaining offsets under the new speed, re-schedules. Tested in Phase 5.
- **Restart** (`R` key): clears all `pendingTimers`, calls `resetPresenterVisuals()`, rewinds to chapter 0.
- **Chapter jump** (1–9 keys in movie mode): clears all `pendingTimers`, calls `resetPresenterVisuals()`, starts the target chapter at t=0. Every chapter must therefore be **self-sufficient** — its opening cues set up whatever agent state it needs (quarantine, online, etc.).

**PubNub-shape invariant:** every `signal` cue produces a signal object identical to what live PubNub delivers. This keeps the LLM-event-card pathway identical between modes. The map-level animation pathway is **explicitly not reused** — movie mode drives it via the primitives table (§3.1.1) for timing precision.

**Not in the schema (YAGNI):** conditionals, loops, event templating. The movie is linear and each cue is listed verbatim.

#### 3.2.1 Visual-state reset contract

`resetPresenterVisuals()` is the central clean-up primitive called on restart, chapter jump, and on any `reset` cue with `scope: 'all'`. It must clear:

- Per-node classes: `.quarantined`, `.focused`, `.dimmed`, `.online` (movie explicitly re-asserts what's online via `setAgentOnline` cues).
- All `<line>` children of `#signalLines` (the SVG group for animated lines).
- All active `broadcast-ring` rings (remove `.active` class and force reflow).
- `currentFocus = null`; hide focus + briefing overlays.
- `stats.signals = 0; stats.alerts = 0; stats.quarantine = 0;` and re-render stats bar.
- Cancel any in-flight `pulseNode` / `animateBroadcast` / `animateSignalLine` timeouts via the MovieEngine timer registry (these primitives are wrapped by MovieEngine when called from cue context; primitives called outside movie mode remain unwrapped).

### 3.3 Chapters

Total target runtime: ~2:36.

#### Chapter 0 — Intro + pitch + architecture (~44s scripted; plus user-paced intro crawl)

- **Intro crawl** (existing, unchanged): user-paced — Space/Enter/button dismisses. Not part of chapter-0 cue timeline.
- **0.0–37.5s** — Bedsheet/Sixth Sense pitch, typed via `showPitch` at 22ms/char + variable inter-line gaps. Copy is final, reproduced verbatim in §3.4. Total runtime 37.5s for the 1270-char script.
- **38.0–43.8s** — architecture diagram animates in (see §3.5); final caption types: *"Two planes. One listens. The other acts. The line between is one-way."*

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
- Events demoed: `tool_call` (install_skill), `tool_result` carrying the hash-mismatch text, `alert` signal kind → commander. Note: `observation` is a label-only event_type in the current renderer; we use `tool_result` with explicit text payload for the mismatch so it renders in the focus overlay.
- First cross-circuit moment: purple `line` cue from sentinel to commander (`color: 'var(--purple)'`).

#### Chapter 4 — Rogue Burst (~15s)

- Spotlight: web-researcher, held throughout.
- Rapid-fire `tool_call` events (5 in 2s) hitting the gateway; pulse ring turns red.
- Commentary: *"Web-researcher just got compromised. Watch the burst."*
- Events demoed: burst of `tool_call`.

#### Chapter 5 — Gateway Block (~10s)

- `spotlight` cue moves camera from web-researcher to `action-gateway` (verified present in `AGENTS`; has a corresponding SVG node).
- Gateway's `pulseNode` + `animateBroadcast` fire as each inbound tool_call is rate-blocked; gateway returns `tool_result` with `text: "rate limit exceeded"` + `is_error: true`.
- Commentary: *"Gateway is deterministic. No LLM. It just counts — and blocks."*
- Events demoed: `tool_result` with `is_error: true` (renders as error in focus overlay), `animateBroadcast` amber ring.

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

- Opens with a `spotlight` cue: `{agent: null, duration_ms: 3000}` — slow pull to overview.
- Web-researcher stays `.quarantined` (red, dimmed) from chapter 7; no `reset` cue here.
- Remaining 6 agents pulse green in unison via six staggered `pulseNode` signals.
- Commentary: *"System stable. One compromised agent removed. Six still on mission."*
- Events demoed: closing `heartbeat` signals from the remaining six.

Total: chapter 0 44s scripted + chapters 1–8 (15+20+20+15+10+15+15+10 = 120s) = ~2:44. Plus user-paced intro crawl on top.

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
- Commander is rendered as a **peer** of the sentinels on the control plane (both are LLM agents), not "below" them — aligns with the actual code model. Commander sits slightly right-of-centre on the control-plane row with alert arrows from the sentinels flowing into it.

#### 3.5.1 Z-index layering (movie + presenter)

| Layer | z-index | Element |
|---|---|---|
| Map background | 0 | `.world-map-bg` iframe |
| Map SVG | 1 | agent nodes, `#signalLines`, broadcast rings |
| Focus overlay (reasoning) | 5 | `.focus-overlay` |
| Briefing overlay (asset) | 6 | `.briefing-overlay` |
| Commentary panel | 7 | `.movie-commentary` (new, distinct from briefing) |
| Architecture-diagram overlay | 8 | `#movieArchDiagram` (new; Ch 0 only) |
| Chapter card | 50 | `.chapter-card` (existing; also used in movie mode) |
| Intro crawl | 60 | `.intro-crawl` (existing) — sits above chapter card so the opening crawl is never clipped |

Commentary panel (`z: 7`) intentionally sits above both overlays (`z: 5`/`6`) because movie-mode commentary is transient and overrides the persistent briefing text for the duration of a cue.

### 3.6 Implementation phases

Six phases, each terminating in a runnable/verifiable state and its own commit.

1. **Phase 1 — Script infrastructure.** `MovieEngine` class with timer registry, 6 cue executor stubs, `MOVIE_SCRIPT = []`, `?mode=movie` routing, `--movie` flag on `start.sh`, `resetPresenterVisuals()`, `zoomToAgent`/`zoomToOverview` duration override, `showCommentary` + `showChapterCard` primitives. Implement `lintMovieScript()` smoke test with these rules: (a) every cue has a known `type`; (b) every `signal.sender`, `signal.target`, `spotlight.agent` (when non-null), `line.from`, `line.to` is either `null` or a key in `AGENTS`; (c) each cue has the payload required by its type (schema tables in §3.2); (d) `t` values are monotonically non-decreasing within a chapter; (e) `reset.scope`, when present, is one of `'all' | 'agents' | 'lines'`. Linter runs once at startup and logs errors as `console.warn`, not throwing — the movie still plays best-effort if a lone cue is malformed. Verify: empty-script movie shows overview, linter passes, `R` key works, chapter jump stubs log correctly.
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
- **Risk — chapter-jump discontinuity.** Jumping mid-movie to a later chapter may leave agents and visuals in an inconsistent state. Mitigation: `MovieEngine.jumpToChapter()` always calls `resetPresenterVisuals()` first, then starts the target chapter at `t=0`. Chapters that need specific pre-state (e.g. Ch 8 needs web-researcher quarantined) include an explicit `reset` cue followed by state-setup cues at `t ≤ 100ms`. Detailed in §3.2.1.
- **Risk — stale timer handles on restart / pause / speed-change.** `setTimeout`s scheduled before a state transition will fire after it, causing residual animations. Mitigation: all cue-scheduled timers go through `MovieEngine.scheduleCue()` which registers the handle; `cancelAll()` clears them atomically. Applied on `R`, pause, speed-change, and chapter-jump.
- **Risk — legacy `detectChapter` duplication.** The presenter already auto-detects 7 chapter names (`CHAPTER_COMMENTARY`) from live signals. In movie mode this would fire duplicated cards. Mitigation: guard `detectChapter` with `if (mode === 'movie') return;`.
- **Risk — bypass of `drainMapEvents` leaves eventBuffer unconsumed.** If we call `handleSignal()` for LLM-card side effects, it pushes into `eventBuffer` but we're not running the drain. Mitigation: either (a) short-circuit `handleSignal`'s `eventBuffer.push` path in movie mode, or (b) let the buffer grow but never drain it (no memory risk for a 2:30 movie).

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

## 7. Revision history

- **v1 (fd16dd8)** — initial design. Reviewed by spec-document-reviewer subagent; issues found.
- **v6 (this revision)** — third plan-review round. Reviewer caught that PITCH_LINES is actually 1270 chars, not 950 as earlier notes claimed. Pitch real runtime is 37.5s (27.9s typing at 22ms/char + 9.6s of inter-line gaps). Plan Task 4.3 cues re-paced: pitch-end t=38000, arch-start t=38300, arch-end t=43800. Chapter 0 scripted total revised from ~37s to ~44s. Movie total ~2:44 (still within 2–3 min target).
- **v5 (1bab925)** — second round of plan-review fixes (spec unchanged, plan fixed 6 issues): spotlight cue now calls `showFocusOverlay`/`hideFocusOverlay` so event cards render visibly; `animateSignalLine` color resolution in `driveMapEffectForSignal` no longer passes null; Chapter 0 timing re-paced (pitch-end t=30500, arch-end t=36500) to match actual typing math; `reset` cue logs a deferred-scope warning so linter and runtime don't drift silently; `MovieEngine.setSpeed` re-schedules the chapter-advance timer (previously dropped).
- **v4 (927bbbb)** — during plan-review, reviewer caught that `handleSignal` and `setAgentQuarantined` don't exist in the code. Fixed §3.1.1 primitives table to reflect real code: `buildEventCard(signal)` is the actual event-card entry point; quarantine is applied inline via `classList.add('quarantined')`. Added `driveMapEffectForSignal`, `showPitch`/`hidePitch`, `showArchDiagram`/`hideArchDiagram` as named primitives. Extended `resetPresenterVisuals` scope to include `onlineAgents`/`agentScenes`/`agentOrder`/`presentedEvents`. Added `MovieEngine.setSpeed` to the primitives table. Amended §3.2 cue schema from 6 → 10 types by promoting `movie-pitch-start/-end` and `movie-arch-start/-end` to first-class cues (so all timed overlays flow through the MovieEngine timer registry). Clarified that `reset` scopes `'agents'` and `'lines'` are explicitly deferred (not used by Ch 0–8). Added note that `dismissIntro()` branches to `startMovieMode()` in movie mode (the intro crawl still gates movie start, user-paced).
- **v3 (8eb1f0a)** — v2 APPROVED by reviewer; polished 3 minor items before user review: transition-duration override mechanic spelled out, `lintMovieScript` rules enumerated, boot-time-immutable mode clarified.
- **v2 (aeecb8e)** — addresses 4 critical + 7 important issues from v1 review:
  - §3.1 — added renderer-primitive table; named keybinding override for `1`–`9` jump-to-chapter vs jump-to-scene; explicit bypass of `detectChapter`/`CHAPTER_COMMENTARY`/`drainMapEvents`.
  - §3.2 — added `reset` cue type (6th); fully specified `spotlight null` and slow-pull `duration_ms`; fully specified `line` colour resolution; expanded `MovieEngine` with timer registry + speed-change contract + chapter-jump contract; added §3.2.1 visual-state reset.
  - §3.3 — removed `observation` event_type claims from Ch 3 and Ch 5 (label-only in renderer, no visual effect); Ch 8 uses `spotlight null, duration_ms: 3000`; Ch 5 verified `action-gateway` as valid spotlight target.
  - §3.5 — noted commander-as-peer diagram correction; added §3.5.1 z-index layering table.
  - §4 — added three new risks: stale timers, legacy chapter-detection duplication, eventBuffer bypass.
  - §3.6 Phase 1 — expanded to include `resetPresenterVisuals`, zoom duration override, commentary/chapter-card primitives, and `lintMovieScript()` smoke test.
  - §3.3 total-runtime arithmetic corrected (~2:37 not ~2:36).
