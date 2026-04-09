# Session Handoff — 2026-02-20

## Branch
`feature/sixth-sense` — PR #4 at https://github.com/sivang/bedsheet/pull/4

## What Was Done This Session

### 1. Committed and pushed all previous session work
- GCP transpiler fixes (3 bugs: duplicate imports, missing module constants, hyphenated agent names)
- `examples/sentinel-gcp/` — bedsheet source agents for the sentinel demo
- Pre-commit fixed: installed `pre-commit` into venv via `uv` (system Python virtualenv was broken due to missing `platformdirs`)

### 2. Code review (via superpowers:code-reviewer)
Full review run against the branch. Two critical issues found and fixed:

**Critical #1 — `claim_incident` logic inverted**
- `_claimed_incidents.add(incident_id)` was never called before broadcasting
- Result: claim always returned `False` in production
- Fix: optimistic add before broadcast; `_handle_claim` evicts if a lower-name competitor wins
- Test rewritten to exercise the real path; second test added for tiebreak eviction

**Critical #2 — `signals()` Protocol signature mismatch**
- Protocol declared `def`, both implementations use `async def` (async generators)
- Fix: kept `def` in Protocol (correct for calling convention) but added docstring clarifying the async generator pattern

**Important fixes also done:**
- Removed unreachable `if not gcp.project` dead code in `validate()`
- Renamed `_parallel_sweep` → `_sequential_sweep` in template (was backed by SequentialAgent)
- Updated `_determine_orchestration` docstring: `"parallel"` → `"sequential"`

### 3. New tests — real coverage for transpiler
`tests/test_source_extractor_constants.py` — 10 tests verifying:
- Dict, set, int, `os.path` constants extracted correctly from functions that reference them
- Functions with no module references return empty
- Every extracted constant is valid parseable Python
- `from os import os` regression explicitly tested
- No duplicate imports

### 4. Removed broken deploy artifacts
`examples/sentinel-gcp/deploy/gcp/` deleted — broken Dockerfile (wrong `uv pip install` syntax), missing `ddgs` dependency, untested Terraform. Will be re-added when actually verified end-to-end.

### 5. Detailed internals documentation
`docs/sixth-sense-internals.html` — honest deep-dive covering:
- PubNub thread→asyncio bridge (`call_soon_threadsafe`)
- Channel namespacing scheme
- Compact serialization + silent truncation limitation
- Signal loop dispatch logic line-by-line
- Request/response flow diagram
- Claim/release protocol and its known race condition (>250ms latency)
- **Why SequentialAgent not ParallelAgent** — documented as a rate-limit workaround for free-tier Gemini, not an architectural decision. Production Vertex AI deployments should use `ParallelAgent`. A `sub_agent_mode` config option in `bedsheet.yaml` is the right long-term fix.
- Full known limitations table

### 6. CI fixed
`bedsheet/llm/factory.py` and `bedsheet/llm/gemini.py` were sitting untracked. `bedsheet/llm/__init__.py` imported both, causing `ModuleNotFoundError` on CI collection. Committed both files.

## Current PR State
- 5 commits ahead of main
- 307 tests passing
- lint: pass, typecheck: pass, tests: should be green (last push fixed CI)
- Broken deploy artifacts removed
- All code review critical issues resolved

## Unresolved / Next Session

### Session stickiness / Redis for Cloud Run
User asked about using Redis to persist ADK sessions so Cloud Run can scale to zero (cost savings). This came from a review on `sivang/zeteo` PR #17 — same pattern applies to bedsheet GCP deployments.

**The problem:** ADK's default session service is in-memory (`InMemorySessionService`). When Cloud Run scales to zero and restarts, all conversation history is lost. `--session-affinity` (sticky routing) is contradictory with `--min-instances 0`.

**Bedsheet already has:** `RedisMemory` in `bedsheet/memory/redis.py` for bedsheet agents directly. But ADK has its own session layer, separate from bedsheet's Memory protocol.

**What needs investigation:**
- Does ADK offer a database-backed session service? (likely yes — check ADK docs)
- Should the GCP transpiler emit Redis session config when a `session_store: redis` option is set in `bedsheet.yaml`?
- Or is this only relevant when running bedsheet agents directly on Cloud Run (not ADK)?

### examples/sentinel-gcp/deploy/gcp/
Deleted this session. Needs to be re-generated and actually verified:
1. Fix `pyproject.toml` to include `ddgs` dependency
2. Fix `Dockerfile` to use `uv sync` not `uv pip install -r pyproject.toml`
3. Actually build the Docker image locally and verify it starts
4. Only commit after verified

### PR merge decision
PR #4 is ready for review. Once @claude is added as a collaborator on sivang/bedsheet, the review request can be completed. After review, merge to main and cut a new version.

## Files Changed This Session (vs main)
- `bedsheet/sense/` — Sixth Sense module (all new)
- `bedsheet/deploy/source_extractor.py` — transpiler bug fixes
- `bedsheet/deploy/introspect.py` — module_constants field
- `bedsheet/deploy/targets/gcp.py` — dependency collection, validate fix, orchestration rename
- `bedsheet/deploy/templates/gcp/agent.py.j2` — sweep rename
- `bedsheet/deploy/templates/gcp/__init__.py.j2` — explicit re-exports
- `bedsheet/llm/factory.py` — new
- `bedsheet/llm/gemini.py` — new
- `bedsheet/llm/__init__.py` — exports factory + gemini
- `tests/test_sense.py` — claim tests rewritten + new tiebreak test
- `tests/test_source_extractor_constants.py` — new
- `tests/test_deploy_targets_gcp.py` — orchestration assertion updated
- `docs/sixth-sense-internals.html` — new
- `.pre-commit-config.yaml` — types-redis added, default_language_version set
- `examples/sentinel-gcp/agents/` — bedsheet source agents
- `examples/sentinel-gcp/bedsheet.yaml` — demo config
