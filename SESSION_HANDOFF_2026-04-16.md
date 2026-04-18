# Session Handoff — 2026-04-16

## Session Summary

Three-day arc (2026-04-14 through 2026-04-16) plus a long polish-and-rework session on 04-16 afternoon/evening. Executed a full brainstorm → spec → plan → implement loop for **Movie Mode** on the Sentinel Presenter, then iterated heavily with the user on visual and interaction polish. PR #8 is open with ~30 commits of movie-mode work.

## Major Polish Iteration (after first doomsday on 04-16)

After the initial movie-mode implementation (commits `8996c13` → `43845aa`), the user went into a polish iteration session that surfaced and fixed many issues. Key threads:

### Pacing & visual feel
- **Zoom depth** iterated 2.5× → 1.75× → 1.3× based on user feedback that zoom was "far too much."
- **Zoom transition duration** 0.8s → 1.5s for a stately push-in.
- **Chapter inter-gap** 0 → 1.5s → 3s of breathing room between chapters.
- **Non-focused agents** `.dimmed` opacity iterated 0.2 → 0 → 0.3 (back to visible; panel overlap isn't solved by hiding agents, it's solved by DnD positioning).
- **Architecture-diagram dwell** 5s → 20s so the audience has time to actually read the two-plane teaching caption.

### Font + typography
- Bedsheet pitch font iterated 14px → 70px → 66px → 50px → 34px (final, matched to BEDSHEET title).
- Intro crawl text bumped to 34px to match — unified type-scale across pitch, intro, and BEDSHEET title.
- Arch-diagram caption is multi-line with inter-line gaps.
- `[object Object]` bug in tool_call cards — `buildEventCard` now JSON-stringifies object tool_inputs; tool_result reads `.result || .text` for movie/live schema compatibility.

### Director mode (major restructure)
- **Chapters do not auto-advance.** User presses `N` / Right-arrow to move between chapters. `P` / Left-arrow goes back.
- **Beats within a chapter are also director-gated.** A chapter splits at each spotlight cue into "beats" — each beat requires a separate `N` to advance to the next spotlight. Non-spotlight cues (signals, commentary) play automatically inside each beat. Chapter 3 (Normal Operations) has 4 beats; Chapter 7 (Quarantine) has 2; etc.
- `?mode=movie&auto=1` opts into kiosk-style auto-play. Director mode is the default for movie.
- Old chapter 0 split: Chapter 0 (Bedsheet Brief, auto-plays pitch) + Chapter 1 (Architecture, director-triggered).
- Chapter-card titles renumbered 1–8 → 2–9 to match new array indices.

### DnD panel positioner (replaces auto-placer)
- `findPanelPosition` heuristic **removed entirely** (+ `rectsOverlap`, + `lastFocusRect` state).
- Press `E` to enter edit mode: panels get dashed cyan outline, chapter pauses (cancelAll), grab cursor. Drag panels anywhere.
- Every drag-release **saves to localStorage instantly** (key: `bedsheet.panelPositions`).
- Press `X`: browser downloads `panel-positions.json`, also printed to console + copied to clipboard. Move the file to `docs/panel-positions.json` and commit to make positions portable across machines.
- Boot sequence: synchronous localStorage load → async fetch of `docs/panel-positions.json` → override if present.
- **Positions are GLOBAL (HUD-style)**, one per panel, not per-agent. The per-agent model was a premature abstraction; the user correctly called it out.
- **Fallback defaults**: focus top-right (60%, 8%), briefing bottom-left (5%, 55%). Safe corners, non-overlapping, used when no authored positions exist.

### Shrink-and-reopen spotlight transitions
- Panels collapse to `scale(0.1) opacity: 0` for the full zoom duration, then grow back at the new agent's position.
- Unified across every spotlight start (not just agent→agent transitions) for visual consistency.
- Fix a CSS cascade bug: `.transitioning` rule had to be placed AFTER both `.focus-overlay.visible` and `.briefing-overlay.visible` declarations in the stylesheet, plus `!important` on transform+opacity, for specificity reasons.

### Music toggle + director hint
- `M` toggles ambient music (on/off). Preference persists in `localStorage['bedsheet.ambientMuted']`.
- Director hint moved from bottom-right to bottom-left (copyright footer lives bottom-right in cinematic mode).
- Hint reads: `▸ N advances — E edits panels — M mutes music`.

### Bug fixes
- start.sh `--movie` no longer launches the 7-agent fleet (was wasteful; movie is fully synthetic).
- `--help` flag added to start.sh with color-grouped modes/modifiers/misc sections.
- `showCommentary` + `showChapterCard` name-collision fix with presenter originals (commit `6beaa40`).
- `spotlight` cue now sets `currentFocus` in movie mode (was null → DnD saves silently failed).
- Typing-sound epoch guard (commit `418c11e`) — race condition where `hidePitch` clears a pending setTimeout AFTER the keystroke sound fires.
- Worktree-vs-main-workspace Bash tool discipline: always `cd` to worktree path explicitly, or use absolute paths.

## What Shipped

1. **Presenter pin + overlay fixes** (early in the session, before the movie work):
   - Agent pins counter-scale on zoom (1.3× effective at 2.5× viewport zoom) so they don't drown panels.
   - Briefing and reasoning windows converted from `max-height` to fixed `height` so they scroll internally instead of expanding as text types.
   - Reasoning (focus) overlay now positioned closer to the pin than the briefing.
   - Seven agent pins moved onto land (SVG-bbox-derived coordinates). Largest move: supply-chain-sentinel y=386→459 (was in Indian Ocean).
   - Widened avoid-rect around the pin (180×95) and increased panel gap to 90px so briefing no longer clips pin labels ("sentinel-commander" etc.).

2. **Movie Mode** — full implementation. See `PROJECT_STATUS.md` 2026-04-14/16 entry for the detail. Key artifacts:
   - `docs/sentinel-presenter.html` — MovieEngine, 10-cue schema, 9 chapters, pitch copy, architecture diagram SVG, CSS (~1,100 added lines).
   - `examples/agent-sentinel/start.sh` — `--movie` flag.
   - `docs/sentinel-presenter-guide.html` — Movie Mode section + Authoring a New Chapter recipe.
   - `docs/superpowers/specs/2026-04-14-sentinel-presenter-movie-mode-design.md` — v1 → v6.
   - `docs/superpowers/plans/2026-04-14-sentinel-presenter-movie-mode.md` — v1 → v6.
   - README — pointer to the presenter guide added under Agent Sentinel links.

## The "Why" — architectural decisions

1. **Movie mode as a peer mode, not a fork of replay.** Replay depends on recorded LLM sessions (the sentinel recordings are short, ~49 events; re-recording needs a paid Gemini key). Movie mode bypasses all of it — synthetic signals, fully authored, works from `file://`. Three peer modes: `live`, `replay`, `movie`. Boot-time-immutable, selected by `?mode=X` or flag.

2. **Reuse `handleSignal()` renderer path — except we don't.** The spec originally said "movie cues call `handleSignal` to reuse LLM-event-card rendering." Plan review proved `handleSignal` doesn't exist — actual entry point is `handleMessage(event)` with a PubNub wrapper, and it has unwanted side effects (scene collection, `eventBuffer` push, `collecting` timer). Solution: call `buildEventCard(signal)` directly and append to `#focusBody`. Simpler and avoids the side-effect surface.

3. **Chapter-based structure over signal-chain or three-act.** Reused the 7 chapter phases the presenter already detects (`CHAPTER_COMMENTARY`), plus chapter-0 intro and chapter-8 stable. Each chapter is an independent unit an author can write in isolation. `1`–`8` keys jump to chapter. `R` restarts.

4. **Bypass `drainMapEvents` for map effects.** `drainMapEvents` paces at 800ms — would coalesce Chapter 4's 5-in-2s burst. MovieEngine drives map primitives (`pulseNode`, `animateBroadcast`, `animateSignalLine`) directly via `driveMapEffectForSignal`, with `handleMessage` left out of the path entirely. `eventBuffer` grows but never drains — acceptable memory cost for a 2:30 movie.

5. **Ten cue types including four Chapter-0-only overlays.** Original 6 cues (`chapter-card`, `spotlight`, `signal`, `commentary`, `line`, `reset`) plus `movie-pitch-start/-end` and `movie-arch-start/-end`. Promoting the overlay cues to schema-level (rather than direct function calls from a chapter-0 bootstrap) keeps them flowing through `MovieEngine.scheduleCue` so pause/speed/restart/chapter-jump tear them down correctly.

6. **Pitch copy in DARPA-white-paper register.** User rejected startup-pitch phrasing. Final version leads with "Bedsheet was created out of a single understanding" and uses military verbs throughout (*engineered, fielded, operate, stands upon*). Sixth Sense is positioned as the headline differentiator — first real-time HA bus in any agent framework, contrasted explicitly with A2A ("not HPC"). Locked verbatim in spec §3.4.

## Gotchas

1. **`handleSignal` fiction.** Spec v1 + plan v1 cited this function. Reviewer caught that the real entry is `handleMessage(event)`. **Takeaway:** during brainstorm/spec, name every external function; have the reviewer subagent verify every citation.

2. **Plan-review found bugs 4 and 3 levels deep.** Spec review caught 3 critical + 7 important issues in v1. Plan review v1 → v2 caught 3 more (most notably `spotlight` not calling `showFocusOverlay`, which would have made event cards render into an invisible container). Plan v2 → v3 caught the pitch char-count error (1270, not 950). **Takeaway:** review loops are not optional. They caught real bugs every round.

3. **Background-tab animation throttling.** When verifying in the claude-in-chrome automation tab, CSS transitions with currentTime stuck at 0; `setTimeout`-driven typing didn't advance. The code works in a foreground tab. **Takeaway:** browser automation is for checking state changes, not animation timing.

4. **Chapter 0 must NOT wait for the intro crawl.** Original plan assumed 8s crawl was part of chapter 0's cue timeline. Actually the crawl is user-dismissed (Space/Enter/button) BEFORE `startMovieMode()` fires. Chapter 0 starts at t=0 after dismissal. Chapter 0 cue timeline doesn't include the crawl window.

5. **Chapter-jump must reset visuals, but Chapter 8 deliberately doesn't.** Chapters 1–7 each depend on a fresh map state when jumped-to. Chapter 8's story — *"six agents still on mission"* with web-researcher greyed out — only works correctly when played in sequence after Chapter 7's quarantine. Jumping to Chapter 8 alone shows an overview with no quarantined agent. Documented in the guide's authoring tips.

6. **CSS transition override needs restore.** `zoomToAgent`/`zoomToOverview` now accept `{durationMs}`. Implementation sets `element.style.transitionDuration = '3000ms'` before the transform, then restores the empty string on `transitionend` (with a `duration + 100ms` fallback) so subsequent non-movie zooms use the stylesheet default.

7. **`MovieEngine.setSpeed` must re-schedule the chapter-advance timer.** `cancelAll()` clears every pending timer including the chapter-advance `setTimeout`. Re-scheduling only the cues would leave the chapter to hang at its end. Fixed in v5.

## Next Actions (priority order)

1. **Author panel positions for the movie.** Press `E` once per chapter with a spotlight, drag focus + briefing panels to ideal positions (they're GLOBAL now, so one drag set applies everywhere). Press `X`, move `~/Downloads/panel-positions.json` to `docs/`. Commit. This locks in the visual composition for every future movie playthrough.

2. **Rerun `pr-review-toolkit` on PR #8** — earlier review (commit range before the polish session) was done; the polish iteration added ~30 commits that haven't been reviewed. Focus agents: `code-reviewer`, `silent-failure-hunter`, `comment-analyzer`.

3. **Apply any fixes from toolkit**, re-push, watch CI.

4. **Merge the PR** — squash merge. Remember the post-squash gotcha: `git fetch && git reset --hard origin/main`, NOT `git pull`.

5. **Clean up the worktree** after merge: `git worktree remove .worktrees/sentinel-presenter`.

6. **Optional follow-ups (parked):**
   - Re-record the sentinel demo at 60-90s with a paid Gemini key (unblocks replay mode for full chapters).
   - Simplify `agent-sentinel-security-architecture.html` (user flagged as overly dense).
   - Install `@claude` GitHub bot (`.github/workflows/claude-review.yml` + `ANTHROPIC_API_KEY` secret).
   - v0.5.0 release bump — codebase is substantially ahead of PyPI v0.4.8.
   - Rename ClawHub → OpenClaw across code, briefings, and copy.
   - Auto-save panel-positions.json via POST endpoint (would need to upgrade start.sh's HTTP server from `python3 -m http.server` to something POST-capable).

## Version Control State

- **Branch:** `feature/sentinel-presenter` at `c4eabbf`
- **PR:** [#8](https://github.com/sivang/bedsheet/pull/8) — open
- **Ahead of main:** ~70 commits total (movie-mode implementation + polish iteration session)
- **All pushed** to `origin/feature/sentinel-presenter`
- **Worktree:** `.worktrees/sentinel-presenter/` preserved
- **Uncommitted:** clean working tree

## Resume commands (next session)

```bash
cd .worktrees/sentinel-presenter
source .venv/bin/activate

# Check PR state
gh pr view 8 --comments

# Author panel positions (top priority remaining item):
examples/agent-sentinel/start.sh --movie
# → dismiss intro → N through chapters with spotlights → E to edit → drag focus + briefing
# → X to export JSON → mv ~/Downloads/panel-positions.json docs/ → commit

# Sanity checks
pytest tests/ -q --ignore=tests/integration --ignore=tests/test_memory_redis.py
```

## Key runtime controls (for next-session orientation)

| Key | Movie-mode action |
|---|---|
| `N` / `→` | Advance one beat (within chapter) or one chapter (between chapters) |
| `P` / `←` | Go back one beat or one chapter |
| `1`–`9` | Jump to chapter |
| `R` | Restart from chapter 0 |
| `Shift+1`–`5` | Speed 0.5× / 1× / 1.5× / 2× / 3× |
| `E` | Toggle panel-edit mode (pauses chapter, allows drag) |
| `X` | Export panel positions to disk (downloads panel-positions.json) |
| `C` | Clear all saved positions (in edit mode) |
| `M` | Toggle ambient music |
| `F` | Fullscreen |

---
*Session ended: 2026-04-16*
