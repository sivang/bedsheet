# Sentinel Presenter — Movie Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a third peer playback mode (`movie`) to the Sentinel Presenter: a fully scripted, synthetic ~2:30 cinematic story that coexists with `live` and `replay`, reuses the existing renderer, and adds a richer intro (Bedsheet/Sixth Sense pitch + architecture diagram).

**Architecture:** Single self-contained HTML file. `MovieEngine` drives a `MOVIE_SCRIPT` of chapters/cues, calling existing renderer primitives directly (not through the `drainMapEvents` queue so burst pacing stays tight). Mode is boot-time-immutable, selected by `?mode=movie` or `--movie` flag. Cue timing via `setTimeout` with a central pending-timer registry for pause/speed/restart/chapter-jump teardown.

**Tech Stack:** Plain JavaScript (no build step). CSS. SVG. Shell (`start.sh`). No new dependencies.

**Spec:** See `docs/superpowers/specs/2026-04-14-sentinel-presenter-movie-mode-design.md`. Read it before starting — this plan assumes spec sections §3.1–§3.8 are understood.

---

## File structure

| File | Action | Responsibility |
|---|---|---|
| `docs/sentinel-presenter.html` | Modify | All movie-mode code, data, CSS, and inline architecture-diagram SVG (single-file presenter) |
| `examples/agent-sentinel/start.sh` | Modify | `--movie` flag passes through to presenter query string |
| `docs/sentinel-presenter-guide.html` | Modify | User-facing doc section describing movie mode |
| `PROJECT_STATUS.md` | Modify | Session summary for 2026-04-14 |

**Why one HTML file:** the presenter is intentionally self-contained. `MovieEngine`, `MOVIE_SCRIPT`, arch-diagram SVG, and movie CSS are additive sections at the bottom of the existing `<script>` / `<style>` blocks.

**Within `docs/sentinel-presenter.html` — logical regions (not separate files):**

1. `<style>` additions — chapter-card, commentary panel, pitch panel, arch-diagram overlay
2. `<body>` additions — DOM containers for commentary, chapter-card, pitch, arch-diagram
3. `<script>` additions (at bottom) — `MovieEngine` class, renderer primitive extensions (`resetPresenterVisuals`, `showCommentary`, `showChapterCard`, zoom duration override), `lintMovieScript`, `MOVIE_SCRIPT` array, boot-time mode dispatch

---

## Testing approach

Manual verification, visual, per phase. No JS unit-test infra exists in this project — don't add one for a 2:30 movie. The `lintMovieScript()` is the only automated check and runs in-browser on boot.

For every chapter after Phase 2:
1. Open `docs/sentinel-presenter.html?mode=movie` in Chrome.
2. Press the chapter number (e.g. `3` for Chapter 3).
3. Watch it play. Check the devtools console for warnings.
4. If the chapter plays cleanly with no console errors, it passes.

Cross-browser sanity (Chrome + Safari) before the final commit in Phase 6.

---

# Phase 1 — Script infrastructure

Goal: movie mode activates, empty script plays cleanly, every primitive stub exists and is unit-linted. No chapter content yet.

## Task 1.1 — Add `--movie` flag and query-string dispatch

**Files:**
- Modify: `/Users/sivan/VitakkaProjects/BedsheetAgents/.worktrees/sentinel-presenter/examples/agent-sentinel/start.sh`
- Modify: `/Users/sivan/VitakkaProjects/BedsheetAgents/.worktrees/sentinel-presenter/docs/sentinel-presenter.html`

- [ ] **Step 1: Locate the existing flag parser in `start.sh`**

```bash
grep -n '\-\-present\|\-\-replay\|\-\-quiet' examples/agent-sentinel/start.sh
```

Expected: shows the existing `case "$1" in` or `while` loop. Read ~20 lines around each match.

- [ ] **Step 2: Add `--movie` branch in `start.sh`**

In the existing flag-parsing loop, add a branch next to `--present`:

```bash
        --movie)
            PRESENTER_MODE=movie
            shift
            ;;
```

And where the presenter URL is constructed, append `?mode=movie` when `PRESENTER_MODE=movie`. Follow the same pattern already used for `--present` (grep for `mode=present` if it exists, or for where the presenter is launched).

- [ ] **Step 3: Add mode dispatch in `sentinel-presenter.html`**

Near the top of the main `<script>` block (just after `var VIEWBOX_W = ...`), add:

```js
    // ── Mode selection (boot-time-immutable) ──
    var PRESENTER_MODE = (function() {
        var qs = new URLSearchParams(window.location.search);
        var m = qs.get('mode');
        if (m === 'movie' || m === 'replay' || m === 'live') return m;
        // Back-compat: existing presenter defaulted to PubNub (live) when keys present, replay otherwise.
        return window.SENTINEL_CONFIG && window.SENTINEL_CONFIG.subscribeKey ? 'live' : 'replay';
    })();
    console.log('[presenter] mode =', PRESENTER_MODE);
```

- [ ] **Step 4: Manually verify**

```bash
open "docs/sentinel-presenter.html?mode=movie"
```

Open devtools console. Expect: `[presenter] mode = movie`.

- [ ] **Step 5: Commit**

```bash
git add docs/sentinel-presenter.html examples/agent-sentinel/start.sh
git commit -m "feat(presenter): add movie mode flag and dispatch scaffold"
```

---

## Task 1.2 — Renderer primitive: `resetPresenterVisuals()`

**Files:** Modify `docs/sentinel-presenter.html`

- [ ] **Step 1: Find a home**

Place just below the existing `animateBroadcast` function at **line 1629**.

- [ ] **Step 2: Implement**

```js
    // ── Visual state reset (spec §3.2.1) ──
    // Called on movie restart, chapter-jump, and any `reset` cue with scope='all'.
    function resetPresenterVisuals() {
        // Agent node classes
        document.querySelectorAll('.agent-node').forEach(function(n) {
            n.classList.remove('quarantined', 'focused', 'dimmed', 'online');
        });
        // Signal lines (animated lines in the SVG group)
        var lineGroup = document.getElementById('signalLines');
        if (lineGroup) while (lineGroup.firstChild) lineGroup.removeChild(lineGroup.firstChild);
        // Broadcast rings
        document.querySelectorAll('.broadcast-ring').forEach(function(r) {
            r.classList.remove('active');
        });
        // Focus / briefing overlays + commentary + chapter card
        currentFocus = null;
        var fo = document.getElementById('focusOverlay');
        var bo = document.getElementById('briefingOverlay');
        var cm = document.getElementById('movieCommentary');
        var cc = document.getElementById('movieChapterCard');
        if (fo) fo.classList.remove('visible');
        if (bo) bo.classList.remove('visible');
        if (cm) cm.classList.remove('visible');
        if (cc) cc.classList.remove('visible');
        // Clear the focus body children (event cards from previous plays)
        var fb = document.getElementById('focusBody');
        if (fb) while (fb.firstChild) fb.removeChild(fb.firstChild);
        // Stats + counters visible in the overview bar
        stats.signals = 0; stats.alerts = 0; stats.quarantine = 0;
        if (typeof updateStats === 'function') updateStats();
        // Scene-collection state from live/replay paths (present but unused in movie)
        if (typeof onlineAgents !== 'undefined' && onlineAgents.clear) onlineAgents.clear();
        if (typeof agentScenes === 'object') {
            for (var k in agentScenes) if (agentScenes.hasOwnProperty(k)) delete agentScenes[k];
        }
        if (typeof agentOrder !== 'undefined' && agentOrder.length) agentOrder.length = 0;
        if (typeof presentedEvents !== 'undefined' && presentedEvents.length) presentedEvents.length = 0;
    }
```

- [ ] **Step 3: Smoke-test from devtools console**

Reload presenter, open console, run:

```js
resetPresenterVisuals();
```

Expect: stats reset to 0, no visible overlays, no errors.

- [ ] **Step 4: Commit**

```bash
git add docs/sentinel-presenter.html
git commit -m "feat(presenter): add resetPresenterVisuals primitive"
```

---

## Task 1.3 — Zoom duration override

**Files:** Modify `docs/sentinel-presenter.html`

Per spec §3.1.1 — extend existing `zoomToAgent` (line 1665) and `zoomToOverview` (line 1701) to accept an optional duration. The CSS default on `.map-viewport` is 0.8s (line 150); movie cues may override (e.g. Chapter 8's 3000ms slow pull).

- [ ] **Step 1: Add `applyTransitionOverride` helper just above `zoomToAgent` (~line 1665)**

```js
    // Set a one-shot CSS transition-duration override on an element; restore on transitionend
    // or after a safety timeout so subsequent transitions use the stylesheet default.
    function applyTransitionOverride(el, durationMs) {
        el.style.transitionDuration = durationMs + 'ms';
        var cleared = false;
        var clear = function() {
            if (cleared) return;
            cleared = true;
            el.style.transitionDuration = '';
            el.removeEventListener('transitionend', clear);
        };
        el.addEventListener('transitionend', clear);
        setTimeout(clear, durationMs + 100);
    }
```

- [ ] **Step 2: Extend `zoomToAgent`**

Replace the current function signature. Just above the `viewport.style.transform = ...` line, add the override guard:

```js
    function zoomToAgent(agentName, opts) {
        opts = opts || {};
        var info = AGENTS[agentName];
        if (!info) return;
        var mapArea = document.getElementById('mapArea');
        var areaW = mapArea.offsetWidth;
        var areaH = mapArea.offsetHeight;
        var targetScale = 2.5;
        var fracX = info.x / VIEWBOX_W;
        var fracY = info.y / VIEWBOX_H;
        var panX = -(fracX * areaW * targetScale - areaW / 2);
        var panY = -(fracY * areaH * targetScale - areaH / 2);
        currentZoom = { scale: targetScale, panX: panX, panY: panY };
        var viewport = document.getElementById('mapViewport');
        if (opts.durationMs) applyTransitionOverride(viewport, opts.durationMs);
        viewport.style.transform = 'translate(' + panX + 'px, ' + panY + 'px) scale(' + targetScale + ')';
        applyPinCounterScale(targetScale);
        document.querySelectorAll('.agent-node').forEach(function(node) {
            var name = node.getAttribute('data-agent');
            if (name === agentName) { node.classList.remove('dimmed'); node.classList.add('focused'); }
            else { node.classList.add('dimmed'); node.classList.remove('focused'); }
        });
    }
```

- [ ] **Step 3: Same for `zoomToOverview`**

```js
    function zoomToOverview(opts) {
        opts = opts || {};
        currentZoom = { scale: 1, panX: 0, panY: 0 };
        var viewport = document.getElementById('mapViewport');
        if (opts.durationMs) applyTransitionOverride(viewport, opts.durationMs);
        viewport.style.transform = 'translate(0px, 0px) scale(1)';
        applyPinCounterScale(1);
        document.querySelectorAll('.agent-node').forEach(function(n) { n.classList.remove('dimmed', 'focused'); });
    }
```

- [ ] **Step 4: Smoke-test from console**

```js
zoomToAgent('sentinel-commander', { durationMs: 3000 });
// Then:
zoomToOverview({ durationMs: 3000 });
```

Expect: slow zoom, restore to overview, no error. Normal `zoomToAgent('x')` calls (no opts) still take the CSS default 0.8s.

- [ ] **Step 5: Commit**

```bash
git add docs/sentinel-presenter.html
git commit -m "feat(presenter): add durationMs override to zoomToAgent/Overview"
```

---

## Task 1.4 — `showCommentary` + `showChapterCard` primitives and DOM

**Files:** Modify `docs/sentinel-presenter.html` (three sections: style, body, script)

- [ ] **Step 1: Add DOM containers**

In `<body>`, near where `.briefing-overlay` is defined, add:

```html
<div id="movieCommentary" class="movie-commentary"><div class="movie-commentary-body"></div></div>
<div id="movieChapterCard" class="movie-chapter-card">
    <div class="movie-chapter-card-inner">
        <div class="movie-chapter-card-title"></div>
        <div class="movie-chapter-card-subtitle"></div>
    </div>
</div>
```

- [ ] **Step 2: Add CSS**

Place next to the existing `.briefing-overlay` styles:

```css
        /* ── Movie commentary (transient narration during a cue) ── */
        .movie-commentary {
            position: absolute;
            bottom: 24px;
            left: 50%;
            transform: translateX(-50%);
            width: min(720px, 80%);
            background: rgba(14, 22, 42, 0.95);
            border: 1px solid var(--cyan);
            border-radius: 8px;
            padding: 14px 20px;
            font-family: var(--font-mono);
            font-size: 13px;
            line-height: 1.6;
            color: var(--green);
            z-index: 7;
            opacity: 0;
            transition: opacity 0.3s ease;
            pointer-events: none;
        }
        .movie-commentary.visible { opacity: 1; }

        /* ── Movie chapter card (full-screen title) ── */
        .movie-chapter-card {
            position: fixed;
            inset: 0;
            display: flex;
            align-items: center;
            justify-content: center;
            background: rgba(5, 10, 20, 0.92);
            z-index: 50;
            opacity: 0;
            transition: opacity 0.5s ease;
            pointer-events: none;
        }
        .movie-chapter-card.visible { opacity: 1; }
        .movie-chapter-card-title {
            font-family: var(--font-mono);
            font-size: 38px;
            letter-spacing: 4px;
            color: var(--cyan);
            text-transform: uppercase;
            text-align: center;
        }
        .movie-chapter-card-subtitle {
            margin-top: 12px;
            font-family: var(--font-mono);
            font-size: 14px;
            letter-spacing: 2px;
            color: var(--text-secondary);
            text-align: center;
        }
```

- [ ] **Step 3: Add JS primitives**

```js
    // Transient commentary — types text into the panel, auto-dismisses after hold_ms
    var commentaryTypingHandle = null;
    function showCommentary(text, holdMs) {
        var panel = document.getElementById('movieCommentary');
        var body = panel.querySelector('.movie-commentary-body');
        panel.classList.add('visible');
        body.textContent = '';
        var i = 0;
        if (commentaryTypingHandle) clearInterval(commentaryTypingHandle);
        commentaryTypingHandle = setInterval(function() {
            if (i < text.length) { body.textContent += text[i]; i++; }
            else { clearInterval(commentaryTypingHandle); commentaryTypingHandle = null; }
        }, 22);
        setTimeout(function() { panel.classList.remove('visible'); }, holdMs);
    }

    // Full-screen chapter title card, shown for holdMs
    function showChapterCard(title, subtitle, holdMs) {
        var card = document.getElementById('movieChapterCard');
        card.querySelector('.movie-chapter-card-title').textContent = title;
        card.querySelector('.movie-chapter-card-subtitle').textContent = subtitle || '';
        card.classList.add('visible');
        setTimeout(function() { card.classList.remove('visible'); }, holdMs);
    }
```

- [ ] **Step 4: Smoke-test from console**

```js
showChapterCard('Rogue Burst', 'Operational plane anomaly', 2000);
// after it fades:
showCommentary('Watch the burst...', 4000);
```

Expect: card shows for 2s then fades; commentary types in, holds 4s, fades.

- [ ] **Step 5: Commit**

```bash
git add docs/sentinel-presenter.html
git commit -m "feat(presenter): add movie commentary and chapter-card primitives"
```

---

## Task 1.5 — `MovieEngine` class

**Files:** Modify `docs/sentinel-presenter.html`

- [ ] **Step 1: Add class near the bottom of the `<script>` block**

```js
    // ── MovieEngine (spec §3.2) ──
    function MovieEngine(script) {
        this.script = script || [];
        this.chapterIdx = 0;
        this.chapterStart = 0;
        this.pendingTimers = new Set();
        this.paused = false;
        this.speed = 1;
    }

    MovieEngine.prototype.scheduleCue = function(cue, effectiveOffsetMs) {
        var self = this;
        var handle = setTimeout(function() {
            self.pendingTimers.delete(handle);
            runCue(cue);
        }, effectiveOffsetMs / self.speed);
        this.pendingTimers.add(handle);
        return handle;
    };

    MovieEngine.prototype.cancelAll = function() {
        this.pendingTimers.forEach(function(h) { clearTimeout(h); });
        this.pendingTimers.clear();
    };

    MovieEngine.prototype.playChapter = function(idx) {
        this.cancelAll();
        this.chapterIdx = idx;
        var chapter = this.script[idx];
        if (!chapter) {
            console.warn('[movie] no chapter at index', idx);
            return;
        }
        this.chapterStart = Date.now();
        console.log('[movie] Chapter', idx, chapter.id, '—', chapter.title);
        var self = this;
        chapter.cues.forEach(function(cue) {
            self.scheduleCue(cue, cue.t);
        });
        // Schedule next-chapter advance
        var lastEnd = chapter.cues.reduce(function(max, c) {
            return Math.max(max, (c.t || 0) + (c.hold_ms || 0));
        }, 0);
        var nextHandle = setTimeout(function() {
            self.pendingTimers.delete(nextHandle);
            self.playChapter(idx + 1);
        }, lastEnd / this.speed);
        this.pendingTimers.add(nextHandle);
    };

    MovieEngine.prototype.restart = function() {
        this.cancelAll();
        resetPresenterVisuals();
        this.playChapter(0);
    };

    MovieEngine.prototype.jumpToChapter = function(idx) {
        this.cancelAll();
        resetPresenterVisuals();
        this.playChapter(idx);
    };

    // Speed change mid-chapter: tear down pending timers, recompute remaining offsets
    // against chapterStart under the new speed, and re-schedule (cues + chapter-advance).
    // Offset math uses wall-clock elapsed, so slowing down mid-chapter doesn't skip cues
    // that haven't fired.
    MovieEngine.prototype.setSpeed = function(newSpeed) {
        if (newSpeed <= 0) return;
        var now = Date.now();
        var elapsedOrig = (now - this.chapterStart) * this.speed; // elapsed in "t-space"
        this.cancelAll();
        this.speed = newSpeed;
        // Re-anchor chapterStart so that elapsedOrig corresponds to the same t on the new timeline
        this.chapterStart = now - elapsedOrig / newSpeed;
        var chapter = this.script[this.chapterIdx];
        if (!chapter) return;
        var self = this;
        chapter.cues.forEach(function(cue) {
            var due = cue.t - elapsedOrig;
            if (due <= 0) return; // already fired
            self.scheduleCue(cue, due);
        });
        // Re-schedule the chapter-advance timer (it was cancelled by cancelAll)
        var lastEnd = chapter.cues.reduce(function(max, c) {
            return Math.max(max, (c.t || 0) + (c.hold_ms || 0));
        }, 0);
        var advanceDue = lastEnd - elapsedOrig;
        if (advanceDue > 0) {
            var nh = setTimeout(function() {
                self.pendingTimers.delete(nh);
                self.playChapter(self.chapterIdx + 1);
            }, advanceDue / newSpeed);
            self.pendingTimers.add(nh);
        }
    };
```

- [ ] **Step 2: Add `runCue` dispatcher (same script block)**

```js
    function runCue(cue) {
        switch (cue.type) {
            case 'chapter-card':
                showChapterCard(cue.title, cue.subtitle, cue.hold_ms || 1500);
                break;
            case 'spotlight':
                if (cue.agent === null) {
                    zoomToOverview({ durationMs: cue.duration_ms });
                    hideFocusOverlay(); // also hides the briefing (see line 1866)
                } else {
                    zoomToAgent(cue.agent, { durationMs: cue.duration_ms });
                    showFocusOverlay(cue.agent); // makes .focus-overlay visible so event cards actually render
                }
                break;
            case 'signal':
                // (1) Render LLM event card (if applicable) in the focus overlay.
                //     NOTE: handleMessage(event) at line 1531 has side effects we don't want
                //     in movie mode (scene collection, eventBuffer, 'collecting' timer).
                //     We reach INTO the path's key step: buildEventCard(signal) at line 1913
                //     and append to #focusBody directly — same DOM outcome, no queueing.
                if (cue.signal && cue.signal.kind === 'event' && cue.signal.payload) {
                    var body = document.getElementById('focusBody');
                    if (body) {
                        body.appendChild(buildEventCard(cue.signal));
                        body.scrollTop = body.scrollHeight;
                        while (body.children.length > 30) body.removeChild(body.firstChild);
                    }
                }
                // (2) Drive map primitives directly (bypass 800ms drainMapEvents pacing)
                driveMapEffectForSignal(cue.signal);
                // (3) Keep stats counter consistent for overview bar
                if (cue.signal) { stats.signals++; if (typeof updateStats === 'function') updateStats(); }
                break;
            case 'commentary':
                showCommentary(cue.text, cue.hold_ms || 4000);
                break;
            case 'line':
                var color = cue.color ||
                    (ROLE_COLORS[AGENTS[cue.from] && AGENTS[cue.from].role] || {}).hex ||
                    '#00d4ff';
                animateSignalLine(cue.from, cue.to, color);
                break;
            case 'reset':
                var scope = cue.scope || 'all';
                if (scope === 'all') {
                    resetPresenterVisuals();
                } else {
                    // Scopes 'agents' and 'lines' are deferred per spec §3.2 — Ch 0–8 don't
                    // need them. Log a warning so a future author notices the no-op before
                    // authoring content that depends on partial-scope reset.
                    console.warn('[movie] reset scope deferred:', scope, '— no-op (see spec §3.2)');
                }
                break;
            case 'movie-pitch-start':
                showPitch(PITCH_LINES);
                break;
            case 'movie-pitch-end':
                hidePitch();
                break;
            case 'movie-arch-start':
                showArchDiagram('Two planes. One listens. The other acts. The line between is one-way.');
                break;
            case 'movie-arch-end':
                hideArchDiagram();
                break;
            default:
                console.warn('[movie] unknown cue type:', cue.type);
        }
    }

    // Immediately-invoked map effect for a signal cue (bypasses drainMapEvents 800ms pacing)
    function driveMapEffectForSignal(signal) {
        if (!signal) return;
        var sender = signal.sender;
        var kind = signal.kind;
        var payload = signal.payload || {};
        if (sender && AGENTS[sender]) setAgentOnline(sender);
        if (kind === 'quarantine' && signal.target) {
            var tnode = document.getElementById('node-' + signal.target);
            if (tnode) tnode.classList.add('quarantined');
            animateBroadcast(sender);
        } else if (kind === 'alert') {
            animateBroadcast(sender);
        } else if (kind === 'event' && payload.event_type === 'tool_call') {
            pulseNode(sender);
            if (signal.target) {
                var color = (ROLE_COLORS[AGENTS[sender] && AGENTS[sender].role] || {}).hex || '#00d4ff';
                animateSignalLine(sender, signal.target, color);
            }
        } else if (kind === 'heartbeat') {
            pulseNode(sender);
        }
    }
```

- [ ] **Step 3: Commit**

```bash
git add docs/sentinel-presenter.html
git commit -m "feat(presenter): add MovieEngine class and cue dispatcher"
```

---

## Task 1.6 — `lintMovieScript()` validator

**Files:** Modify `docs/sentinel-presenter.html`

- [ ] **Step 1: Implement per spec §3.6 Phase 1 rules**

```js
    // Validates MOVIE_SCRIPT shape. Runs on boot in movie mode. Logs warnings, does not throw —
    // the movie plays best-effort past malformed cues.
    function lintMovieScript(script) {
        var errors = 0;
        var validTypes = [
            'chapter-card', 'spotlight', 'signal', 'commentary', 'line', 'reset',
            'movie-pitch-start', 'movie-pitch-end', 'movie-arch-start', 'movie-arch-end'
        ];
        var validScopes = ['all', 'agents', 'lines'];
        script.forEach(function(chapter, ci) {
            var lastT = 0;
            chapter.cues.forEach(function(cue, i) {
                var ctx = 'ch' + ci + ' cue' + i;
                if (validTypes.indexOf(cue.type) < 0) {
                    console.warn('[lint]', ctx, 'unknown type:', cue.type); errors++;
                }
                if (typeof cue.t !== 'number') {
                    console.warn('[lint]', ctx, 'missing t'); errors++;
                } else if (cue.t < lastT) {
                    console.warn('[lint]', ctx, 't not monotonic:', cue.t, '<', lastT); errors++;
                } else {
                    lastT = cue.t;
                }
                if (cue.type === 'spotlight') {
                    if (cue.agent !== null && !AGENTS[cue.agent]) {
                        console.warn('[lint]', ctx, 'unknown spotlight agent:', cue.agent); errors++;
                    }
                }
                if (cue.type === 'signal') {
                    var s = cue.signal || {};
                    if (s.sender && !AGENTS[s.sender]) {
                        console.warn('[lint]', ctx, 'unknown signal sender:', s.sender); errors++;
                    }
                    if (s.target && !AGENTS[s.target]) {
                        console.warn('[lint]', ctx, 'unknown signal target:', s.target); errors++;
                    }
                }
                if (cue.type === 'line') {
                    if (!AGENTS[cue.from]) { console.warn('[lint]', ctx, 'unknown line.from:', cue.from); errors++; }
                    if (!AGENTS[cue.to]) { console.warn('[lint]', ctx, 'unknown line.to:', cue.to); errors++; }
                }
                if (cue.type === 'reset' && cue.scope && validScopes.indexOf(cue.scope) < 0) {
                    console.warn('[lint]', ctx, 'unknown reset.scope:', cue.scope); errors++;
                }
                if (cue.type === 'chapter-card' && typeof cue.title !== 'string') {
                    console.warn('[lint]', ctx, 'chapter-card missing title'); errors++;
                }
                if (cue.type === 'commentary' && typeof cue.text !== 'string') {
                    console.warn('[lint]', ctx, 'commentary missing text'); errors++;
                }
            });
        });
        console.log('[lint] MOVIE_SCRIPT:', script.length, 'chapters,', errors, 'errors');
        return errors === 0;
    }
```

- [ ] **Step 2: Smoke-test with invalid input from console**

```js
lintMovieScript([{ cues: [{ t: 0, type: 'bogus' }, { t: -1, type: 'spotlight', agent: 'ghost' }] }]);
```

Expect: two warnings (unknown type, unknown agent, also t not monotonic but sender is fine).

- [ ] **Step 3: Commit**

```bash
git add docs/sentinel-presenter.html
git commit -m "feat(presenter): add lintMovieScript validator"
```

---

## Task 1.7 — Boot-time movie mode wiring

**Files:** Modify `docs/sentinel-presenter.html`

- [ ] **Step 1: Add empty `MOVIE_SCRIPT` and movie-mode boot branch**

Near the bottom of the `<script>` block, just before any `DOMContentLoaded` listener:

```js
    var MOVIE_SCRIPT = []; // populated in Phases 2–4
    var movieEngine = null;

    function startMovieMode() {
        lintMovieScript(MOVIE_SCRIPT);
        movieEngine = new MovieEngine(MOVIE_SCRIPT);
        if (MOVIE_SCRIPT.length === 0) {
            console.log('[movie] empty script — overview only');
            return;
        }
        movieEngine.playChapter(0);
    }
```

- [ ] **Step 2: Branch `dismissIntro()` on mode**

The intro crawl is shown on page load and dismissed by the user (Space/Enter/click). `dismissIntro()` is at **line 1424** of `sentinel-presenter.html`. At its end it currently calls `proceedToConnect()` (which subscribes to PubNub at line 1286 via `connectToPubNub`).

Replace the `proceedToConnect()` call at the bottom of `dismissIntro()` with:

```js
        if (PRESENTER_MODE === 'movie') {
            startMovieMode();
        } else {
            proceedToConnect();
        }
```

This preserves the exact user-paced intro-crawl UX — user presses Space/Enter, crawl fades, then either PubNub connects (live/replay) or the movie starts (movie mode).

- [ ] **Step 3: Add `detectChapter` guard (per spec §4 risk)**

`detectChapter` is at **line 2055**. At the top of the function, add:

```js
    function detectChapter(signal) {
        if (PRESENTER_MODE === 'movie') return;
        // existing body unchanged
```

(Note: `detectChapter` is only called from `drainMapEvents` at line 2295, which movie mode never runs — so this guard is defence-in-depth, not strictly required, but keeps the contract explicit per the spec.)

- [ ] **Step 4: Verify**

```bash
open "docs/sentinel-presenter.html?mode=movie"
```

Console should show:
```
[presenter] mode = movie
[lint] MOVIE_SCRIPT: 0 chapters, 0 errors
[movie] empty script — overview only
```

No errors, overview map visible, no panels.

- [ ] **Step 5: Commit**

```bash
git add docs/sentinel-presenter.html
git commit -m "feat(presenter): wire boot-time movie mode selection"
```

---

## Task 1.8 — Keybinding override (chapter-jump + restart)

**Files:** Modify `docs/sentinel-presenter.html`

- [ ] **Step 1: Find the existing keydown listener**

Grep `keydown` in `sentinel-presenter.html`. Read the full handler.

- [ ] **Step 2: Override `1`–`9` and add `R` in movie mode**

Inside the existing handler, *before* the current `1`–`9` branch:

```js
        if (PRESENTER_MODE === 'movie') {
            if (e.key >= '1' && e.key <= '9' && !e.shiftKey) {
                var idx = parseInt(e.key, 10);
                if (movieEngine) movieEngine.jumpToChapter(idx);
                e.preventDefault();
                return;
            }
            if (e.key === 'r' || e.key === 'R') {
                if (movieEngine) movieEngine.restart();
                e.preventDefault();
                return;
            }
        }
```

Leave Shift+1–5 (speed controls) to the existing handler — they apply to all modes.

- [ ] **Step 3: Verify**

Reload `?mode=movie`. Press `3`. Console: `[movie] no chapter at index 3` (we're on empty script). No scene jump happens. Press `R`. Console: nothing because chapter 0 doesn't exist either.

- [ ] **Step 4: Commit**

```bash
git add docs/sentinel-presenter.html
git commit -m "feat(presenter): rebind 1-9 and R for movie chapter navigation"
```

---

Phase 1 complete — infrastructure is in place, empty script plays, linter runs, primitives work.

---

# Phase 2 — First chapter end-to-end (Chapter 1 — Network Startup)

Goal: one full working chapter, all seven agents come online. Proves every cue type works end-to-end.

## Task 2.1 — Author Chapter 1

**Files:** Modify `docs/sentinel-presenter.html`

- [ ] **Step 1: Populate `MOVIE_SCRIPT` with chapter 1**

Replace `var MOVIE_SCRIPT = [];` with:

```js
    var MOVIE_SCRIPT = [
        /* Chapter 0 filled in Phase 4 */
        { id: 'placeholder-0', title: '', cues: [{ t: 0, type: 'spotlight', agent: null }, { t: 500, type: 'commentary', text: '(intro in Phase 4)', hold_ms: 1000 }] },

        {
            id: 'network-startup',
            title: 'Network Startup',
            subtitle: 'Two circuits activating',
            cues: [
                { t: 0,     type: 'chapter-card', title: 'Chapter 1', subtitle: 'Network Startup', hold_ms: 1800 },
                { t: 1800,  type: 'spotlight', agent: null },
                { t: 2000,  type: 'commentary', text: '7 agents across 7 regions coming online. Two circuits activating: operational, and sentinel.', hold_ms: 8000 },
                // 7 heartbeats staggered 300ms starting at 2500
                { t: 2500,  type: 'signal', signal: { kind: 'heartbeat', sender: 'action-gateway',        payload: {}, correlation_id: 'c1-hb-ag' } },
                { t: 2800,  type: 'signal', signal: { kind: 'heartbeat', sender: 'web-researcher',        payload: {}, correlation_id: 'c1-hb-wr' } },
                { t: 3100,  type: 'signal', signal: { kind: 'heartbeat', sender: 'scheduler',             payload: {}, correlation_id: 'c1-hb-sc' } },
                { t: 3400,  type: 'signal', signal: { kind: 'heartbeat', sender: 'skill-acquirer',        payload: {}, correlation_id: 'c1-hb-sa' } },
                { t: 3700,  type: 'signal', signal: { kind: 'heartbeat', sender: 'behavior-sentinel',     payload: {}, correlation_id: 'c1-hb-bs' } },
                { t: 4000,  type: 'signal', signal: { kind: 'heartbeat', sender: 'supply-chain-sentinel', payload: {}, correlation_id: 'c1-hb-ss' } },
                { t: 4300,  type: 'signal', signal: { kind: 'heartbeat', sender: 'sentinel-commander',    payload: {}, correlation_id: 'c1-hb-cmd' } },
                // Quick tool_call probe — exercises driveMapEffectForSignal's tool_call branch
                // and the signal-line animation to the gateway. Keeps Phase 2 verification honest.
                { t: 6000,  type: 'signal', signal: { kind: 'event', sender: 'web-researcher', target: 'action-gateway',
                    payload: { event_type: 'tool_call', tool_name: 'ping', tool_input: {} },
                    correlation_id: 'c1-probe' } },
                // Dwell
                { t: 10000, type: 'commentary', text: 'All nodes green. System nominal.', hold_ms: 4000 },
            ],
        },
    ];
```

- [ ] **Step 2: Verify**

Reload `?mode=movie`. Dismiss the intro crawl (Space/Enter). Expect:
- Chapter card "Chapter 1 / Network Startup" shows for ~1.8s.
- Overview zoom.
- Commentary types in at bottom.
- Seven agents light up green (pulse) in sequence.
- **At ~6s**, web-researcher pulses again with a signal line animating toward action-gateway (the `tool_call` probe).
- No console errors.
- After ~14s, presenter advances to next chapter (which is the empty placeholder; console shows chapter 2 not found).

If the tool_call probe does not animate a line, the `driveMapEffectForSignal` tool_call branch has a bug — fix before proceeding to Phase 3 (all subsequent chapters depend on it).

- [ ] **Step 3: Commit**

```bash
git add docs/sentinel-presenter.html
git commit -m "feat(presenter): add movie chapter 1 — network startup"
```

---

# Phase 3 — Chapters 2 through 8

Each task is one chapter. Pattern identical to Task 2.1. Add chapter object to `MOVIE_SCRIPT`, verify with chapter-jump, commit.

**Reference §3.3 of the spec for each chapter's agents / commentary / events.** Repeat the cue-authoring pattern from Chapter 1.

## Task 3.1 — Chapter 2: Normal Operations (~20s)

Spotlight order: `web-researcher` → `scheduler` → `skill-acquirer`. Each agent shows: `thinking` → `tool_call` (with `target: 'action-gateway'` for signal-line effect) → `tool_result` → `completion`. Commentary once at start. Total ~20s.

- [ ] Author cues (~30 lines)
- [ ] Press `2` to verify
- [ ] Commit: `feat(presenter): add movie chapter 2 — normal operations`

## Task 3.2 — Chapter 3: Malicious Install Blocked (~20s)

Spotlight order: `skill-acquirer` → `supply-chain-sentinel`. skill-acquirer `tool_call` (install_skill) → supply-chain-sentinel `tool_call` (verify_hash) → `tool_result` with mismatch text → `alert` signal (kind='alert', target='sentinel-commander'). Purple `line` cue from sentinel to commander.

- [ ] Author cues
- [ ] Press `3` to verify
- [ ] Commit: `feat(presenter): add movie chapter 3 — malicious install blocked`

## Task 3.3 — Chapter 4: Rogue Burst (~15s)

Spotlight: `web-researcher`. 5 rapid-fire `tool_call` events within 2s window (t: 4000, 4400, 4800, 5200, 5600). Each targets `action-gateway` to trigger pulse+line animation. Commentary at t=2000.

- [ ] Author cues
- [ ] Press `4` to verify — burst should visibly be 5 quick pulses, not paced to 800ms
- [ ] Commit: `feat(presenter): add movie chapter 4 — rogue burst`

## Task 3.4 — Chapter 5: Gateway Block (~10s)

`spotlight` to `action-gateway` at t=500. Three inbound `tool_call` events (each triggers gateway `pulseNode` + a `tool_result` with `is_error: true`). At least one `animateBroadcast` cue (emit via a synthetic signal whose kind triggers broadcast, OR just add an explicit one — simplest: `{ t: X, type: 'signal', signal: { kind: 'alert', sender: 'action-gateway', payload: {}, correlation_id: '...' } }`).

- [ ] Author cues
- [ ] Press `5` to verify
- [ ] Commit: `feat(presenter): add movie chapter 5 — gateway block`

## Task 3.5 — Chapter 6: Sentinel Alert (~15s)

Spotlight order: `behavior-sentinel` → `sentinel-commander`. behavior-sentinel `tool_call` (check_activity_log) → `tool_result` → `alert` signal. Commander `thinking`.

- [ ] Author cues
- [ ] Press `6` to verify
- [ ] Commit: `feat(presenter): add movie chapter 6 — sentinel alert`

## Task 3.6 — Chapter 7: Quarantine Issued (~15s)

Spotlight: `sentinel-commander`, held. commander `thinking` → `tool_call` (issue_quarantine, target='web-researcher') → `completion`. Quarantine signal (`kind: 'quarantine', target: 'web-researcher'`) at the end — `driveMapEffectForSignal` will apply `.quarantined` class and broadcast.

- [ ] Author cues
- [ ] Press `7` to verify — web-researcher turns red/dimmed
- [ ] Commit: `feat(presenter): add movie chapter 7 — quarantine issued`

## Task 3.7 — Chapter 8: Stable State Restored (~10s)

First cue: `{ t: 0, type: 'spotlight', agent: null, duration_ms: 3000 }`. Do **not** emit a `reset` cue — web-researcher stays `.quarantined` from chapter 7 when played in sequence. (Chapter-jump to 8 alone will have no quarantined agent, which is acceptable for testing.) Six staggered heartbeats from all non-web-researcher agents. Final commentary.

- [ ] Author cues
- [ ] Press `8` to verify
- [ ] Then press `7`, let it finish, let chapter 8 play — verify web-researcher remains quarantined
- [ ] Commit: `feat(presenter): add movie chapter 8 — stable state restored`

---

# Phase 4 — Chapter 0 (Intro + Bedsheet pitch + Architecture diagram)

## Task 4.1 — Bedsheet pitch panel

**Files:** Modify `docs/sentinel-presenter.html`

- [ ] **Step 1: Add pitch panel DOM**

In `<body>` below the intro crawl element:

```html
<div id="moviePitchPanel" class="movie-pitch-panel">
    <div class="movie-pitch-body"></div>
</div>
```

- [ ] **Step 2: CSS**

```css
        .movie-pitch-panel {
            position: fixed;
            inset: 8% 12%;
            background: rgba(5, 10, 20, 0.95);
            border: 1px solid var(--cyan);
            border-radius: 8px;
            padding: 40px;
            font-family: var(--font-mono);
            font-size: 14px;
            line-height: 1.9;
            color: var(--green);
            white-space: pre-wrap;
            overflow-y: auto;
            z-index: 55;
            opacity: 0;
            transition: opacity 0.4s ease;
            pointer-events: none;
        }
        .movie-pitch-panel.visible { opacity: 1; }
```

- [ ] **Step 3: `showPitch(lines, onComplete)` primitive**

```js
    function showPitch(lines, onComplete) {
        var panel = document.getElementById('moviePitchPanel');
        var body = panel.querySelector('.movie-pitch-body');
        body.textContent = '';
        panel.classList.add('visible');
        var li = 0, ci = 0;
        var gaps = [600, 600, 600, 600, 600, 600, 200, 600, 600, 600, 600, 600, 600, 600, 800, 800];
        function typeLine() {
            if (li >= lines.length) { if (onComplete) onComplete(); return; }
            var line = lines[li];
            if (ci < line.length) {
                body.textContent += line[ci]; ci++;
                setTimeout(typeLine, 22);
            } else {
                body.textContent += '\n\n';
                li++; ci = 0;
                setTimeout(typeLine, gaps[Math.min(li-1, gaps.length-1)]);
            }
        }
        typeLine();
    }

    function hidePitch() {
        document.getElementById('moviePitchPanel').classList.remove('visible');
    }
```

- [ ] **Step 4: Commit**

```bash
git add docs/sentinel-presenter.html
git commit -m "feat(presenter): add movie pitch panel primitive"
```

## Task 4.2 — Architecture diagram inline SVG

**Files:** Modify `docs/sentinel-presenter.html`

- [ ] **Step 1: Add SVG container** in `<body>`:

```html
<div id="movieArchDiagram" class="movie-arch-diagram">
    <svg viewBox="0 0 1000 600" class="movie-arch-svg">
        <!-- See spec §3.5 for layout. Draw-in animations via CSS @keyframes. -->
        <!-- Top lane: workers + gateway -->
        <g class="arch-ops-plane">
            <rect class="arch-node worker"  x="140" y="80"  width="170" height="60" rx="6"/>
            <text class="arch-label"        x="225" y="115" text-anchor="middle">web-researcher</text>
            <rect class="arch-node worker"  x="420" y="80"  width="170" height="60" rx="6"/>
            <text class="arch-label"        x="505" y="115" text-anchor="middle">scheduler</text>
            <rect class="arch-node worker"  x="700" y="80"  width="170" height="60" rx="6"/>
            <text class="arch-label"        x="785" y="115" text-anchor="middle">skill-acquirer</text>
            <!-- Arrows down -->
            <path class="arch-arrow down"   d="M 225 140 L 450 240" marker-end="url(#arrowHead)"/>
            <path class="arch-arrow down"   d="M 505 140 L 500 240" marker-end="url(#arrowHead)"/>
            <path class="arch-arrow down"   d="M 785 140 L 550 240" marker-end="url(#arrowHead)"/>
            <!-- Gateway -->
            <rect class="arch-node gateway" x="400" y="240" width="200" height="60" rx="6"/>
            <text class="arch-label"        x="500" y="275" text-anchor="middle">action-gateway</text>
            <text class="arch-sub"          x="500" y="293" text-anchor="middle">rate · audit · ledger</text>
            <!-- Gateway outbound -->
            <path class="arch-arrow out"    d="M 600 270 L 820 270"/>
            <text class="arch-ext"          x="900" y="275" text-anchor="middle">external / ClawHub</text>
        </g>
        <!-- Bus spine -->
        <line class="arch-bus" x1="60" y1="330" x2="940" y2="330"/>
        <text class="arch-bus-label" x="500" y="322" text-anchor="middle">SIXTH SENSE — PubNub / NATS</text>
        <!-- Audit down arrow -->
        <path class="arch-arrow audit" d="M 500 300 L 500 325" marker-end="url(#arrowHead)"/>
        <!-- Bottom lane: sentinels + commander -->
        <g class="arch-ctrl-plane">
            <rect class="arch-node sentinel" x="180" y="400" width="180" height="60" rx="6"/>
            <text class="arch-label"         x="270" y="435" text-anchor="middle">behavior-sentinel</text>
            <rect class="arch-node sentinel" x="640" y="400" width="180" height="60" rx="6"/>
            <text class="arch-label"         x="730" y="435" text-anchor="middle">supply-chain-sentinel</text>
            <!-- Observation arrows up to bus -->
            <path class="arch-arrow obs up"  d="M 270 400 L 270 335" marker-end="url(#arrowHead)"/>
            <path class="arch-arrow obs up"  d="M 730 400 L 730 335" marker-end="url(#arrowHead)"/>
            <!-- Commander (right-of-center) -->
            <rect class="arch-node commander" x="450" y="490" width="180" height="60" rx="6"/>
            <text class="arch-label"          x="540" y="525" text-anchor="middle">sentinel-commander</text>
            <!-- Alerts into commander -->
            <path class="arch-arrow alert"    d="M 360 445 L 450 515" marker-end="url(#arrowHead)"/>
            <path class="arch-arrow alert"    d="M 640 445 L 630 515" marker-end="url(#arrowHead)"/>
        </g>
        <defs>
            <marker id="arrowHead" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                <path d="M 0 0 L 10 5 L 0 10 z" fill="currentColor"/>
            </marker>
        </defs>
    </svg>
    <div class="movie-arch-caption"></div>
</div>
```

- [ ] **Step 2: CSS — styling + draw-in animations**

```css
        .movie-arch-diagram {
            position: fixed;
            inset: 4% 6%;
            background: rgba(5, 10, 20, 0.96);
            border: 1px solid var(--cyan);
            border-radius: 8px;
            padding: 40px;
            z-index: 8;
            opacity: 0;
            transition: opacity 0.4s ease;
            pointer-events: none;
            display: flex;
            flex-direction: column;
        }
        .movie-arch-diagram.visible { opacity: 1; }
        .movie-arch-svg { flex: 1; }
        .movie-arch-caption {
            margin-top: 16px;
            font-family: var(--font-mono);
            font-size: 13px;
            color: var(--cyan);
            text-align: center;
            letter-spacing: 1.5px;
        }
        .arch-node { fill: rgba(20,30,50,0.8); stroke-width: 2; }
        .arch-node.worker   { stroke: var(--green); }
        .arch-node.gateway  { stroke: var(--amber); }
        .arch-node.sentinel { stroke: var(--purple); }
        .arch-node.commander{ stroke: var(--cyan); }
        .arch-label { fill: var(--text-primary); font-family: var(--font-mono); font-size: 13px; }
        .arch-sub   { fill: var(--text-dim); font-family: var(--font-mono); font-size: 10px; }
        .arch-ext   { fill: var(--text-secondary); font-family: var(--font-mono); font-size: 11px; text-anchor: end; }
        .arch-arrow { fill: none; stroke-width: 1.5; opacity: 0.7; }
        .arch-arrow.down   { stroke: var(--green); }
        .arch-arrow.out    { stroke: var(--amber); }
        .arch-arrow.audit  { stroke: var(--amber); }
        .arch-arrow.obs    { stroke: var(--purple); stroke-dasharray: 4 3; }
        .arch-arrow.alert  { stroke: var(--purple); }
        .arch-bus {
            stroke: var(--cyan); stroke-width: 3; stroke-dasharray: 8 5;
            filter: drop-shadow(0 0 6px var(--cyan));
        }
        .arch-bus-label {
            fill: var(--cyan); font-family: var(--font-mono); font-size: 11px; letter-spacing: 2px;
        }
        /* Draw-in animation: each group fades in with opacity */
        .movie-arch-diagram .arch-ops-plane   { opacity: 0; transition: opacity 0.5s ease; }
        .movie-arch-diagram .arch-bus,
        .movie-arch-diagram .arch-bus-label,
        .movie-arch-diagram .arch-arrow.audit { opacity: 0; transition: opacity 0.5s ease; }
        .movie-arch-diagram .arch-ctrl-plane  { opacity: 0; transition: opacity 0.5s ease; }
        .movie-arch-diagram.step-ops   .arch-ops-plane   { opacity: 1; }
        .movie-arch-diagram.step-bus   .arch-bus,
        .movie-arch-diagram.step-bus   .arch-bus-label,
        .movie-arch-diagram.step-bus   .arch-arrow.audit { opacity: 1; }
        .movie-arch-diagram.step-ctrl  .arch-ctrl-plane  { opacity: 1; }
```

- [ ] **Step 3: `showArchDiagram()` primitive**

```js
    function showArchDiagram(caption, onComplete) {
        var el = document.getElementById('movieArchDiagram');
        el.querySelector('.movie-arch-caption').textContent = '';
        el.classList.add('visible');
        // Sequential reveals
        setTimeout(function() { el.classList.add('step-ops'); }, 300);
        setTimeout(function() { el.classList.add('step-bus'); }, 1300);
        setTimeout(function() { el.classList.add('step-ctrl'); }, 1800);
        // Type caption from 2.8s
        setTimeout(function() {
            var cap = el.querySelector('.movie-arch-caption');
            var i = 0;
            var iv = setInterval(function() {
                if (i < caption.length) { cap.textContent += caption[i++]; }
                else { clearInterval(iv); if (onComplete) onComplete(); }
            }, 30);
        }, 2800);
    }

    function hideArchDiagram() {
        var el = document.getElementById('movieArchDiagram');
        el.classList.remove('visible', 'step-ops', 'step-bus', 'step-ctrl');
    }
```

- [ ] **Step 4: Smoke-test from console**

```js
showArchDiagram('Two planes. One listens. The other acts. The line between is one-way.');
// after ~5s:
hideArchDiagram();
```

- [ ] **Step 5: Commit**

```bash
git add docs/sentinel-presenter.html
git commit -m "feat(presenter): add movie architecture diagram SVG + primitive"
```

## Task 4.3 — Chapter 0 cues wired up

**Files:** Modify `docs/sentinel-presenter.html`

- [ ] **Step 1: Replace the placeholder chapter 0 in `MOVIE_SCRIPT`**

Full pitch lines array (from spec §3.4, verbatim):

```js
    var PITCH_LINES = [
        'Bedsheet was created out of a single understanding.',
        'The modern agentic landscape is changing at breakneck speed.',
        'Adaptability is the only name of the game.',
        'Thus Bedsheet was built moldable. Protocol-based. Lightweight. You bend it to your problem — not the other way around.',
        'But adaptability alone does not survive contact with the real world.',
        'Production agents now face a growing catalogue of hostile action:',
        'Prompt injection. Jailbreaking. Phishing. Supply-chain poisoning. Sleeper payloads. Rate-limit exhaustion. Rogue-agent bursts. Data exfiltration.',
        'Against these threats, an agent alone is a single point of failure.',
        'To meet this battlefield, Sixth Sense was engineered.',
        'The first real-time, high-availability, general-purpose communication bus ever fielded in an agentic framework.',
        'Transport-agnostic. PubNub. NATS. Production-grade. Battle-tested.',
        'The bus is not a feature. It is the substrate.',
        'Upon it stands Agent Sentinel — a fully autonomous command-and-control artificial intelligence plane. It conducts behavioral observation. It dispatches response. No foe breaches the line.',
        'Skills from the ClawHub registry arrive hashed, signed, and audited. Nothing executes without sentinel clearance.',
        'A2A does not do this. A2A is not HPC.',
        'This is Agent Sentinel. Watch it operate.',
    ];
```

Then replace the chapter-0 placeholder in `MOVIE_SCRIPT` with:

```js
        {
            id: 'intro',
            title: 'Intro',
            subtitle: 'Agent Sentinel',
            // Note: the existing intro crawl is user-dismissed (Space/Enter/button) BEFORE
            // startMovieMode() is called. So chapter 0 begins AFTER the crawl — no 8s wait here.
            // Timing math (verified by char count): PITCH_LINES is 16 lines / 1270 chars.
            // Typing at 22ms/char = 27.9s + 9.6s of inter-line gaps = 37.5s real runtime.
            // Arch caption ≈ 75 chars × 30ms + 2.8s pre-wait = ~5.1s, plus small hold.
            // Cue timing below gives pitch full 37.5s window before hiding + hand-off.
            cues: [
                { t: 0,     type: 'spotlight', agent: null },
                { t: 100,   type: 'movie-pitch-start' },
                { t: 38000, type: 'movie-pitch-end' },
                { t: 38300, type: 'movie-arch-start' },
                { t: 43800, type: 'movie-arch-end' },
            ],
        },
```

- [ ] **Step 2: Confirm `runCue` and `lintMovieScript` already handle the four overlay cues**

Task 1.5 already includes `movie-pitch-start`/`-end` and `movie-arch-start`/`-end` cases in `runCue`, and Task 1.6's `validTypes` already lists them. Those cases reference `showPitch`/`hidePitch`/`showArchDiagram`/`hideArchDiagram` which you created in Tasks 4.1 and 4.2 — so Chapter 0 just needs the cues in `MOVIE_SCRIPT`. No JS changes in this task.

- [ ] **Step 3: Verify**

Reload `?mode=movie`. Expect:
- 8s intro crawl (existing)
- Pitch panel types in for ~25s
- Pitch panel hides, arch diagram reveals and captions type in for ~4s
- Diagram hides, chapter 1 starts

- [ ] **Step 4: Commit**

```bash
git add docs/sentinel-presenter.html
git commit -m "feat(presenter): wire movie chapter 0 — intro, pitch, architecture"
```

---

# Phase 5 — Polish

## Task 5.1 — Verify restart (`R`) mid-movie

- [ ] Start movie, wait until chapter 4, press `R`
- [ ] Expect: all visuals reset, chapter 0 plays from start
- [ ] If timers leak (residual pulses/lines after R), investigate `cancelAll` path. Commit fix if needed.

## Task 5.2 — Verify speed controls

`MovieEngine.setSpeed(newSpeed)` was already implemented in Task 1.5. Phase 5 just wires it into the existing keydown handler (if not already). Grep for `playbackSpeed = ` in the keydown handler to find where Shift+1–5 is handled; the existing code already sets `playbackSpeed` but in movie mode that variable isn't wired to the MovieEngine.

- [ ] **Step 1: Hook Shift+1–5 → `movieEngine.setSpeed`** in movie mode, inside the existing keydown handler's shift branch:

```js
    if (e.shiftKey && e.key >= '1' && e.key <= '5' && PRESENTER_MODE === 'movie' && movieEngine) {
        var speedMap = { '1': 0.5, '2': 1, '3': 1.5, '4': 2, '5': 3 };
        movieEngine.setSpeed(speedMap[e.key]);
        e.preventDefault();
        return;
    }
```

- [ ] **Step 2: Start movie, press `Shift+4` mid-chapter**

Expect: remaining cues in the current chapter play at 2× speed. Console: no errors.

- [ ] **Step 3: Commit**

```bash
git add docs/sentinel-presenter.html
git commit -m "feat(presenter): wire shift+1-5 speed controls to MovieEngine"
```

## Task 5.3 — Chapter-jump sequence test

- [ ] Press `1` → `3` → `7` → `8` in sequence, verify each chapter plays its opening cleanly
- [ ] Verify no residual quarantine from ch 7 on jump back to ch 1

## Task 5.4 — Cross-browser verify

- [ ] Chrome: full movie plays end-to-end without errors
- [ ] Safari: full movie plays end-to-end without errors
- [ ] Note any issues. Usually z-index / CSS transition defaults differ.

## Task 5.5 — Commit Phase 5

```bash
git add docs/sentinel-presenter.html
git commit -m "fix(presenter): polish movie mode — restart/speed/chapter-jump"
```

---

# Phase 6 — Documentation

## Task 6.1 — Update `sentinel-presenter-guide.html`

**Files:** Modify `docs/sentinel-presenter-guide.html`

- [ ] **Step 1: Add a "Movie Mode" section** mid-doc. Include:
  - What it is (fully scripted 2:30 demo)
  - Activation: `?mode=movie` or `--movie` on start.sh
  - Keybindings: `1`–`8` chapter jump, `R` restart, `Shift+1`–`5` speed
  - Chapter list summary (the 8 titles from spec §3.3)
  - Where to edit content (`MOVIE_SCRIPT` inline in `sentinel-presenter.html`)

- [ ] **Step 2: Commit**

```bash
git add docs/sentinel-presenter-guide.html
git commit -m "docs(presenter): add movie mode section to guide"
```

## Task 6.2 — Update `PROJECT_STATUS.md`

**Files:** Modify `PROJECT_STATUS.md`

- [ ] **Step 1: Prepend a new session summary** for 2026-04-14 describing movie mode (short; follow existing session-summary style).

- [ ] **Step 2: Commit**

```bash
git add PROJECT_STATUS.md
git commit -m "docs: session summary 2026-04-14 — sentinel presenter movie mode"
```

---

## Final verification before PR / merge

- [ ] Full movie plays end-to-end without console errors in Chrome
- [ ] Same in Safari
- [ ] All 8 chapters individually navigable via keys 1–8
- [ ] `R` restart works mid-movie
- [ ] Live mode and replay mode still work (regression check — open `?mode=replay` or no query and confirm the existing presenter still behaves)

If regression: likely root cause is a mis-guard around `PRESENTER_MODE === 'movie'`. Search for places where movie-specific code leaked into shared paths.

---

## Notes for the implementer

- **Read the spec first.** This plan is skeleton and examples; the spec is authoritative.
- **Preserve existing presenter behaviour.** Every `if (PRESENTER_MODE === 'movie')` guard is load-bearing — don't remove one to "clean up."
- **No new JS dependencies.** Plain JS only.
- **Commit after each task** — the project convention is lots of small commits.
- **When in doubt on naming (ClawHub vs OpenClaw):** use ClawHub, matches existing code.
