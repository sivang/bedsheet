# Session Handoff — 2026-04-16

## Session Summary

Three-day arc (2026-04-14 through 2026-04-16) executing a full brainstorm → spec → plan → implement loop for **Movie Mode** on the Sentinel Presenter. Ended with PR #8 open and all 6 phases implemented, tested in-browser, and committed.

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

1. **Run `pr-review-toolkit` on PR #8** before tagging ready. Your memory notes say it's caught real bugs on every past PR. Agents to run: `code-reviewer`, `silent-failure-hunter`, `pr-test-analyzer`, possibly `type-design-analyzer` (though low-value for JS-only work). `comment-analyzer` on the docs changes.

2. **Apply any fixes the toolkit surfaces**, re-push, let CI re-run.

3. **CI will run** test 3.11, test 3.12, lint, typecheck on the PR automatically. Watch it turn green.

4. **Merge the PR** — squash merge per project convention. Remember the post-squash gotcha: use `git fetch && git reset --hard origin/main` after merging, not `git pull` (the memory-noted orphan-commit bug).

5. **Clean up the worktree** after merge: `git worktree remove .worktrees/sentinel-presenter`.

6. **Optional follow-ups (parked):**
   - Re-record the sentinel demo at 60-90s with a paid Gemini key (unblocks replay mode for full chapters).
   - Simplify `agent-sentinel-security-architecture.html` (user flagged this as overly dense — acknowledged as separate side project).
   - Install `@claude` GitHub bot (`.github/workflows/claude-review.yml` + `ANTHROPIC_API_KEY` secret) so future PR reviews work asynchronously.
   - v0.5.0 release bump — codebase is substantially ahead of PyPI v0.4.8.
   - Rename ClawHub → OpenClaw across code, briefings, and copy if the rename is desired (flagged as non-blocking in spec §5).

## Version Control State

- **Branch:** `feature/sentinel-presenter` at `57d3c9d`
- **PR:** [#8](https://github.com/sivang/bedsheet/pull/8) — open, awaiting review
- **Ahead of main:** 40 commits (includes presenter pin/overlay fixes + 6 spec/plan revisions + 16 movie-mode implementation commits + 3 doc commits)
- **All pushed** to `origin/feature/sentinel-presenter`
- **Worktree:** `.worktrees/sentinel-presenter/` preserved per the finishing-branch skill (Option 2)
- **Uncommitted:** `examples/agent-sentinel/data/calendar.json` — pre-existing test-run side effect, NOT shipping with this PR

## Commit to add the handoff file + README link

```bash
cd /Users/sivan/VitakkaProjects/BedsheetAgents/.worktrees/sentinel-presenter
git add SESSION_HANDOFF_2026-04-16.md README.md
git commit -m "docs: session handoff 2026-04-16 — movie mode shipped in PR #8"
git push origin feature/sentinel-presenter
```

## Resume commands (next session)

```bash
cd /Users/sivan/VitakkaProjects/BedsheetAgents/.worktrees/sentinel-presenter
source /Users/sivan/VitakkaProjects/BedsheetAgents/.venv/bin/activate
gh pr view 8 --comments                                  # See any review activity
./start.sh --movie                                       # Visually verify the movie
pytest tests/ -q --ignore=tests/integration --ignore=tests/test_memory_redis.py   # Sanity
```

---
*Session ended: 2026-04-16*
