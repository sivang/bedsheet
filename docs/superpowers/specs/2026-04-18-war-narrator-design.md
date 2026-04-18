# War Narrator — Design Spec

**Date:** 2026-04-18
**Branch:** `feature/war-narrator`
**Enhances:** Agent Sentinel™ movie mode (`docs/sentinel-presenter.html`)

## 1. Goal

Add voiced narration to the Agent Sentinel™ movie mode via a named character — **Colonel Eli Vance**, an intelligence analyst who guides the audience through the demo. The narration explains what's happening on screen, why it matters, and provides background on Bedsheet's architecture. Designed for self-running kiosk displays and screen recordings (YouTube, investor decks).

## 2. Character: Colonel Eli Vance

**Archetype:** Intelligence analyst with military bearing. Cerebral, analytical, explains the "why" behind everything. Treats the audience like they have clearance but need context. Occasionally breaks the fourth wall to explain Bedsheet's architecture. Academic authority, measured delivery — never shouts, never rushes.

**Voice direction (Gemini Director's Notes):** "Seasoned military intelligence analyst giving a classified briefing. Deep, measured voice. Academic weight with military bearing. Dry observations, never melodramatic. When threats escalate, he gets quieter and more precise, not louder."

## 3. TTS: Gemini 3.1 Flash TTS

**Why:** Director's Notes allow natural-language voice direction (no preset voice picker). Billable `GEMINI_API_KEY` already available. Pre-renders to `.mp3` files — zero runtime dependencies.

**API:** Gemini API via `google-genai` SDK (already a project dependency). Model ID must be confirmed at implementation time by listing available models via `client.models.list()` and selecting the TTS-capable flash model. Pin the confirmed ID in `generate.py` as a constant.

**Workflow:** Run `generate.py` once → produces `.mp3` files → commit to repo → movie mode plays them. No API calls at runtime.

## 4. Architecture

### 4.1 File structure

```
docs/war-narrator/
├── script.json          # All narration: text + director's notes per beat
├── generate.py          # Reads script.json → calls Gemini TTS → writes .mp3
└── audio/               # Pre-rendered .mp3 files (committed to repo)
    ├── opening-monologue.mp3
    ├── bedsheet-pitch.mp3
    ├── architecture.mp3
    ├── network-startup.mp3
    ├── startup-to-ops-transition.mp3
    ├── normal-ops.mp3
    ├── ops-to-supply-transition.mp3
    ├── malicious-blocked.mp3
    ├── supply-to-rogue-transition.mp3
    ├── rogue-burst.mp3
    ├── gateway-block.mp3
    ├── sentinel-alert.mp3
    ├── alert-to-quarantine-transition.mp3
    ├── quarantine.mp3
    ├── stable-state.mp3
    └── closing-summary.mp3
```

### 4.2 `script.json` schema

```json
{
  "character": "Colonel Eli Vance",
  "global_director_notes": "Seasoned military intelligence analyst...",
  "beats": [
    {
      "id": "opening-monologue",
      "text": "What you're about to see is a live demonstration...",
      "director_notes": "Opening. Calm authority. Setting the stage.",
      "output_file": "opening-monologue.mp3"
    }
  ]
}
```

Each beat has:
- `id` — unique identifier, matches the `.mp3` filename stem
- `text` — what Vance says
- `director_notes` — per-beat voice direction (appended to global notes)
- `output_file` — output filename in `audio/`
- `chapter_idx` — which `MOVIE_SCRIPT` index this beat belongs to (explicit mapping, no guessing from names)
- `duration_ms` — populated by `generate.py` after rendering (measured from the output `.mp3`). Used to compute `t` offsets for subsequent cues.

Top-level schema also includes `version: 1` for future evolution.

### 4.3 `generate.py`

- Reads `script.json`
- For each beat: calls Gemini 3.1 Flash TTS with `text` + combined director's notes
- Writes `.mp3` to `audio/`
- Skips beats whose `.mp3` already exists (unless `--force` flag)
- Measures duration of each `.mp3` using the `mutagen` library (`mutagen.mp3.MP3(path).info.length`) and writes `duration_ms` back into `script.json`
- Reports a summary table: beat ID, duration, file size
- Requires: `GEMINI_API_KEY` env var, `google-genai` package, `mutagen` package
- **Auth:** Uses `genai.Client(api_key=os.environ["GEMINI_API_KEY"])` (same pattern as `bedsheet/llm/gemini.py`)
- **Retry:** Exponential backoff on 429/RESOURCE_EXHAUSTED errors, same pattern as `GeminiClient._call_with_retry` (15s initial, 1.5x growth, 5 retries)
- **Error handling:** If a beat fails after retries, logs the error and continues to the next beat (partial generation is better than all-or-nothing)

### 4.4 New `audio` cue type in MovieEngine

Added to the existing cue types (`chapter-card`, `spotlight`, `signal`, `commentary`, `line`, `reset`, etc.):

```javascript
{ t: 0, type: 'audio', file: 'war-narrator/audio/opening-monologue.mp3' }
```

**`runCue` handler:**
- Creates `<audio>` element (or reuses a pool)
- Sets `src` to the relative path
- Calls `play()` with error handling (`.catch` logs warning, does not break movie)
- Narration always plays at 1x speed — timing offsets scale with `MovieEngine.speed` but audio playback rate is not altered
- On `<audio>` `ended` event: trigger ambient volume un-duck

**Audio manager (`NarrationManager`):**
- `play(file)` — starts playback, ducks ambient to 5%
- `stopAll()` — pauses and resets all active narration `<audio>` elements. **Called from `MovieEngine.cancelAll()`** (existing method modified to invoke `stopAll()`)
- `onEnded` callback — returns ambient volume to 15% (or 0 if M-key muted)
- Volume: narration at 85%, ambient ducks to 5% while any narration is playing
- Preload: on chapter start, preload that chapter's audio files via `new Audio(src)` with `preload='auto'`

**Ambient duck behavior:**
- Duck triggers on `NarrationManager.play()` — sets `ambientAudio.volume = 0.05`
- Un-duck triggers on `<audio> ended` event OR `NarrationManager.stopAll()` — sets `ambientAudio.volume = 0.15`
- If M-key is muted: both narration and ambient stay at 0 regardless of duck state
- If M-key is pressed during active narration: mutes both immediately. On un-mute: narration resumes at 85%, ambient stays ducked at 5%
- Overlapping narration (chapter gap): `stopAll()` fires before new chapter's audio cue, so previous narration stops and ambient briefly un-ducks before re-ducking. This produces a natural breath between chapters.

**`lintMovieScript` update:** Add `'audio'` to the `validTypes` array so `audio` cues pass validation.

### 4.5 MOVIE_SCRIPT integration

Existing `MOVIE_SCRIPT` array gets `audio` cues added alongside existing cues. Example:

```javascript
{
    id: 'ch1-startup', title: 'Network Startup',
    cues: [
        { t: 0,    type: 'audio',       file: 'war-narrator/audio/ch1-network-startup.mp3' },
        { t: 0,    type: 'chapter-card', title: 'CHAPTER 1', subtitle: 'Network Startup', hold_ms: 2500 },
        { t: 500,  type: 'spotlight',    agent: 'action-gateway' },
        // ... existing cues unchanged
    ]
}
```

Audio cues are additive — no existing cues are moved or modified.

## 5. Narration beats (~18 files)

The `MOVIE_SCRIPT` has 10 chapters at indices 0-9. Beat IDs use the script's `id` field, not index numbers, to avoid ambiguity.

| Beat ID | Script index | Content | Approx duration |
|---------|-------------|---------|----------------|
| `opening-monologue` | 0 | Vance introduces himself, sets the classified briefing tone | 15-20s |
| `bedsheet-pitch` | 0 | What is Bedsheet — distributed agent framework, first real-time HA bus | 20-25s |
| `architecture` | 1 | Two-plane architecture — operational vs control, Sixth Sense bus | 15-20s |
| `network-startup` | 2 | Seven agents deploying, roles explained | 10-15s |
| `startup-to-ops-transition` | — | "Now watch them work..." | 5s |
| `normal-ops` | 3 | Routine operations, gateway mediating all tool calls | 10s |
| `ops-to-supply-transition` | — | "But not everything on the registry is what it claims to be..." | 5s |
| `malicious-blocked` | 4 | Supply chain attack, gateway blocks at trust boundary | 12-15s |
| `supply-to-rogue-transition` | — | "The gateway held. But the next threat won't come from outside..." | 5s |
| `rogue-burst` | 5 | Agent goes rogue, DDoS-like burst pattern | 10-12s |
| `gateway-block` | 6 | Rate limiting kicks in, tamper-proof ledger | 10s |
| `sentinel-alert` | 7 | Behavior sentinel detects anomaly, raises alert | 10-12s |
| `alert-to-quarantine-transition` | — | "The commander has the evidence. Now comes the decision..." | 5s |
| `quarantine` | 8 | Commander correlates, issues quarantine | 12-15s |
| `stable-state` | 9 | Network stabilizes, six agents continue | 8-10s |
| `closing-summary` | 9 | What you just saw, why it matters, Bedsheet's value prop. Plays after the final heartbeat pulse sequence in the `stable-restored` chapter. | 15-20s |

Transition beats (marked `—` for script index) are placed as `audio` cues at the end of the preceding chapter, timed after that chapter's last visual cue.

**Total narration: ~3-4 minutes** (aligns with existing ~2:44 movie length, extended slightly for opening/closing).

## 6. What does NOT change

- **On-screen text** — commentary bar, chapter cards, typed briefing panels, intro crawl all remain exactly as-is. Vance's voice is an independent audio layer.
- **Existing cue types** — no modifications to `chapter-card`, `spotlight`, `signal`, `commentary`, `line`, `reset`, or Chapter-0 overlay cues.
- **`start.sh`** — no new flags. Audio plays automatically in movie mode. The existing `--movie` flag is sufficient.
- **Replay/live modes** — narration is movie-mode only. Replay and live PubNub modes are unaffected.
- **Ambient audio** — `docs/ambient.mp3` continues to work. Ambient volume ducks during narration.

## 7. Mute/volume control

- **M key** already toggles ambient music. Extend it to also mute/unmute narration.
- **No separate narration toggle** — one mute controls all audio. Simplicity over configurability.

## 8. Fallback behavior

- If `.mp3` files are missing (e.g., someone cloned without LFS or the files weren't generated), movie mode plays normally with no audio. No errors, no broken UI. The `audio` cue handler checks if the file loads and silently skips on failure.
- Console warning: `[movie] Narration audio not found: war-narrator/audio/opening-monologue.mp3`

## 9. Dependencies

- **Build-time:** `google-genai` (already in `[dev]` deps), `GEMINI_API_KEY`
- **Runtime:** None. Pre-rendered `.mp3` files are static assets.

## 10. Out of scope

- Real-time TTS (all pre-rendered)
- Multiple characters / dialogue (single narrator only, for now)
- Narration for replay/live modes (movie mode only)
- Subtitle track synced to narration (on-screen text is independent)
- User-facing volume slider UI (M key mute toggle is sufficient)
