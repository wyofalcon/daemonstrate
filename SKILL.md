---
name: daemonstrate
description: Generates and maintains two attractive dark-themed draw.io architecture diagrams for ANY project — a portfolio-facing overview (for recruiters) and a layered deep-dive (for collaborators, returning owners, or AI onboarding). Diff-based incremental updates keep token cost low after the first pass. Trigger this skill whenever the user asks to visualize, diagram, map, chart, or document their project architecture; wants to onboard a recruiter/collaborator/new teammate; mentions their diagrams are stale or missing; mentions draw.io / flowcharts / swimlanes / architecture diagrams; or when no `docs/architecture-portfolio.drawio` + `docs/architecture-detailed.drawio` pair exists in the current repo and the user is working on documentation, onboarding, portfolio, or repo cleanup tasks. Also trigger on explicit phrases like "Daemonstrate", "refresh the architecture diagrams", or "show what this project does".
---

# Daemonstrate

Produces two dark-themed, swimlane-structured `.drawio` diagrams for the **target repo** (resolved below). By default they live under `docs/` in the target repo:

- **`docs/architecture-portfolio.drawio`** — scannable in 10 seconds. For recruiters, portfolios, and "what does this project do" introductions. Shows layers, tech stack badges, headline capabilities.
- **`docs/architecture-detailed.drawio`** — complete enough that a returning collaborator (or AI) can orient without reading the whole codebase. Shows routes, services, tables, jobs, integrations, data flows.

Both use the same swimlane skeleton so a reader can move between them without getting lost.

## Path resolution

Resolve these paths once at the start of every run:

- **`SKILL_DIR`** — the directory containing this `SKILL.md`. You already know it because you just loaded this file. All bundled scripts (`drawio_builder.py`, `install-hooks.sh`) live at `$SKILL_DIR/scripts/`. **Never hardcode an absolute path** — this skill must work on any machine.
- **`TARGET_REPO`** — the repo being diagrammed. Default: the current working directory's git root (`git rev-parse --show-toplevel`). Override: if the caller explicitly gave you a different repo path, use that.
- **`OUT_DIR`** — where diagrams are written. Default: `$TARGET_REPO/docs/`. Override: if the caller explicitly gave you a different output directory (e.g., during an evaluation run), use that instead — and in that case *do not* also write into `$TARGET_REPO/docs/`.

Before invoking the builder or installer, confirm the resolved paths — mention them in your first user-facing status message, **or** echo them into the run's report file if the context is non-interactive (hook, eval, script). Either way, make the paths visible so a misrouted run is caught early.

**All working artifacts respect `$OUT_DIR`** — not just the two diagrams and the state file, but the intermediate `graph-spec.json`, any report/log, any scratch files. Never drop working files into `$TARGET_REPO` even if OUT_DIR differs from the default.

## Interactive vs. non-interactive runs

The skill is invoked in two modes and needs sensible defaults for both:

- **Interactive** — a human is on the other end (normal chat). Ask before installing the hook, ask before overwriting hand-edited diagrams, surface resolved paths in chat.
- **Non-interactive** — triggered by the post-commit hook, a CI job, an `expo run:android`-style automation, or an evaluation harness. No prompts are possible. Apply these defaults:
  - Hook install: **skip** (assume the caller controls hooks).
  - Hand-edited diagram detected: save proposed output as `architecture-*.proposed.drawio` alongside the original, do **not** overwrite. Log the conflict.
  - All status messages go to `$OUT_DIR/daemonstrate-run.log` instead of chat.

Detect interactive mode by checking whether the caller gave you a real conversational context (a user turn above) vs. a one-shot prompt from `claude -p` / an eval agent. When in doubt, prefer the non-interactive defaults — they're strictly safer.

## Why two diagrams, and why draw.io

A portfolio diagram that tries to show everything ends up illegible. A deep-dive diagram that only shows layers tells a collaborator nothing. They serve different audiences and should be tuned separately.

Draw.io (`.drawio` XML) is chosen because: (1) GitHub renders it inline when the companion `.svg` export exists, (2) the XML is text-diffable (reviewable in PRs), (3) users can open and hand-edit in diagrams.net without new tooling. The state sidecar `.daemonstrate-state.json` tracks which files fed into which swimlane so the *next* run only re-examines changed layers.

## Decision: first-run vs. incremental

Before doing anything expensive, check what exists in `$OUT_DIR`:

```
$OUT_DIR/architecture-portfolio.drawio
$OUT_DIR/architecture-detailed.drawio
$OUT_DIR/.daemonstrate-state.json
```

- **Any missing** → first-run mode (full exploration).
- **All present** → incremental mode (diff since `state.lastSha`).

If the diagrams exist but the state file is gone, treat as first-run — we have no way to know what was captured.

## First-run workflow

### Step 1 — Detect tech stack

Read manifests that exist in the repo root and major subdirectories:

- JS/TS: `package.json` (all of them, including subdirs like `client/`, `mobile/`, `server/`)
- Python: `pyproject.toml`, `requirements.txt`, `Pipfile`
- Go: `go.mod`
- Rust: `Cargo.toml`
- Ruby: `Gemfile`
- Java/Kotlin: `pom.xml`, `build.gradle(.kts)`
- Elixir: `mix.exs`
- PHP: `composer.json`

From these, extract: languages, frameworks (React, Express, Django, Rails, etc.), databases, and notable libs. This populates the **tech badge** set.

Also glance at `Dockerfile`, `docker-compose.yml`, CI config (`.github/workflows/*`), and `.env.example` to pick up infra + environment shape.

### Step 2 — Classify layers

Walk the top two directory levels and classify each significant dir into a **layer**. The common layer vocabulary:

| Layer | Typical markers |
|---|---|
| **Frontend** | `client/`, `web/`, `ui/`, React/Vue/Svelte deps, `public/`, `index.html` |
| **Mobile** | `mobile/`, `ios/`, `android/`, Expo/React Native deps |
| **Backend / API** | `server/`, `api/`, `routes/`, Express/Fastify/Django deps |
| **Data** | `migrations/`, `prisma/`, `schema.sql`, `models/`, SQL files |
| **Jobs / Workers** | `cron`, `scheduler`, `workers/`, `queues/`, BullMQ/Celery |
| **Integrations** | SDK deps (Stripe, Twilio, Gemini, OpenAI, Firebase, AWS…) |
| **Infra** | `Dockerfile*`, `docker-compose*`, `.github/workflows/`, `terraform/`, `k8s/` |
| **Docs / Assets** | `docs/`, `assets/` — usually *not* shown in diagrams |

Not every project has every layer. Omit empty ones. If a project only has one layer, still render swimlanes — a single lane with depth is clearer than a free-for-all graph.

**Disambiguating adjacent-looking files.** Many projects co-locate orchestration logic with thin SDK adapters (e.g. `server/services/` holding both `note-pipeline.js` and `sms.js`). Use this heuristic:

- **Integrations** = files whose job is to *talk to an external system* (Twilio, Stripe, Gemini, Expo Push, OAuth). Usually thin wrappers around a third-party SDK.
- **Jobs / Workers** = files that *orchestrate our own business logic on a schedule or queue* (categorization pipelines, alert schedulers, cron handlers).

A pipeline that calls a Twilio wrapper lives in **Jobs**; the wrapper itself lives in **Integrations**. Edges between them are fine and expected.

### Step 3 — Explore each layer

There are two exploration strategies; pick based on context, not a hard rule.

**Inline exploration** (default for most runs): Glob + Grep + Read directly from the main agent, one layer at a time. Fast for small-to-medium repos (under ~50 source files per layer) and for budget-constrained runs. A 7-layer repo can be fully mapped inline in ~10 minutes.

**Parallel subagent exploration** (opt-in for large repos): Dispatch one Explore subagent per layer in a single message, when **all** of the following hold:
- The repo is large (many hundreds of source files, multiple services, or a monorepo).
- The conversation is interactive so the user can wait on subagent fan-out.
- You are confident the layer boundaries are clean enough for independent exploration.

When you do dispatch subagents, each gets a focused slice so its context stays compact. Do not recurse — the dispatched subagents explore inline.

**If you're being invoked from a hook, an eval run, or a script → always explore inline.** Subagent fan-out is not worth the overhead and is hard to reason about in those contexts.

Whether you explore inline or via subagents, use the same layer probe. If inline, prompt yourself with this template; if dispatching subagents, this is the subagent's brief:

> You are mapping the **{layer}** of a `{tech}` project for an architecture diagram. Explore `{paths}`. Return JSON matching `references/layer-schema.md`:
> - `capabilities`: 3-6 short phrases describing what *users* (or callers) can do via this layer
> - `key_nodes`: 6-12 structural nodes (components, routes, tables, jobs) with `id`, `label`, `file_path`, optional `detail`
> - `internal_edges`: edges between nodes in this layer
> - `external_edges`: edges this layer extends to *other* layers, referenced by layer name + node label
> - `tech_badges`: the specific tech this layer uses (e.g., `["React 19", "Vite", "React Router 7"]`)
> Keep labels under 4 words. No prose. JSON only.


### Step 4 — Generate the two diagrams

Read `references/drawio-format.md` (XML structure, swimlane pattern) and `references/dark-theme-palette.md` (colors) once.

Assemble a single **graph spec** (JSON) describing both diagrams' content, then pipe it to `scripts/drawio_builder.py` which emits valid `.drawio` XML for each. **Do not hand-write the full XML** — it's repetitive and error-prone; the builder handles IDs, layout math, and style strings.

Run the builder (resolve the script path from `$SKILL_DIR`, not a hardcoded absolute):

```bash
python "$SKILL_DIR/scripts/drawio_builder.py" \
  --spec graph-spec.json \
  --out-portfolio "$OUT_DIR/architecture-portfolio.drawio" \
  --out-detailed "$OUT_DIR/architecture-detailed.drawio"
```

Resolve the Python binary portably:
- Unix/macOS: `command -v python3 || command -v python`
- Windows (Git Bash): `command -v python` (both `python` and `py -3` work); or `where python` in CMD/PowerShell.
- Minimum: Python 3.8 with stdlib only. The builder has no external dependencies.

If no Python is available at all, fall through and hand-write the XML using `references/drawio-format.md` — slower and more error-prone, but workable.

**Portfolio content rules:**
- Header: project name + one-line pitch (pulled from README H1 + first paragraph, or `package.json` `description`).
- One swimlane per layer, horizontal.
- Inside each lane: 3-6 **capability pills** (not file names). Examples: "Google OAuth + cookie auth", "SMS intake via Twilio", "Offline SQLite + delta sync".
- Tech badge row along each lane's top edge.
- 4-8 cross-layer edges showing the headline data flows (label them: "JWT cookie", "REST /api", "SMS webhook", etc.).
- Leave whitespace. A recruiter spends under 15 seconds.

**Detailed content rules:**
- Same swimlane skeleton, same colors (helps readers switch between).
- Inside each lane: structural nodes from `key_nodes` (routes, services, tables, jobs).
- File paths shown below labels in smaller text where helpful.
- Edges labeled with *what* flows (HTTP verb + path, event name, DB table).
- Include Jobs/Workers and Integrations lanes even if small — that's where collaborators get surprised.

### Step 5 — Write state file

Write `$OUT_DIR/.daemonstrate-state.json`:

```json
{
  "version": 1,
  "lastSha": "<current HEAD SHA>",
  "generatedAt": "<ISO 8601>",
  "techStack": ["React 19", "Express 5", "Postgres 16", "…"],
  "layers": {
    "frontend": {
      "files": ["client/src/**/*.jsx", "client/package.json"],
      "checksum": "<sha256 of concatenated file mtimes + paths>"
    },
    "…": {}
  }
}
```

The `files` list stores the **actual file paths** discovered, not just globs — this is what enables diff detection next run.

### Step 6 — Offer to install the post-commit hook

Ask the user once:

> Want me to install a post-commit hook that runs Daemonstrate after each commit? It'll use incremental mode, so cost per commit is low.

If yes, run `bash "$SKILL_DIR/scripts/install-hooks.sh" "$TARGET_REPO"`. The script:
1. Backs up any existing `.git/hooks/post-commit` to `.post-commit.bak`.
2. Writes a new hook that calls `claude -p "..."` (natural-language prompt matching this skill's description) in the background, non-blocking, with a lock file to prevent overlap.
3. Makes it executable (`chmod +x`).

Only install into `$TARGET_REPO`, never into `$OUT_DIR` when they differ (e.g., during evaluation).

If they decline, note in the state file so we don't ask again.

## Incremental (update) workflow

### Step 1 — Load state

Read `$OUT_DIR/.daemonstrate-state.json`. Get `lastSha` and the layer→files map.

### Step 2 — Diff

```bash
git diff --name-only <lastSha> HEAD
```

Also include untracked-but-staged changes if the hook runs mid-workflow: `git status --porcelain`.

### Step 3 — Classify changed files

For each changed file, find which layer(s) it belongs to based on the state's file lists and the layer markers from `Step 2` above. A file can belong to multiple layers (e.g., a migration that's referenced from both Backend and Data views).

### Step 4 — Re-explore only changed layers

Dispatch subagents only for layers with changes. Pass them the previous layer snapshot + a list of changed files so they can produce a **delta**, not a full re-map:

> You previously produced `{previous layer JSON}`. The following files have changed: `{list}`. Produce an **updated** layer JSON reflecting additions, removals, and label changes. Preserve existing node IDs where the concept still exists (so diagram positions stay stable).

### Step 5 — Rebuild diagrams

Merge deltas into the full graph spec, re-run `drawio_builder.py`. The builder preserves node IDs across regens so reviewers see minimal XML diffs in PRs.

### Step 6 — Update state

Bump `lastSha` to current `HEAD`, update changed-layer file lists, rewrite state file.

## Preserving user edits

If the user hand-edits a `.drawio` file outside Daemonstrate, their change should not be silently blown away. Before overwriting either diagram, check:

```
mtime($OUT_DIR/architecture-*.drawio) > state.generatedAt + 60s ?
```

If yes, the diagram has been touched by a human. Ask before overwriting:

> `architecture-portfolio.drawio` looks hand-edited since last generation. Overwrite, or save my proposed version as `architecture-portfolio.proposed.drawio` for you to merge manually?

Default to the non-destructive option on unclear input. Note: file mtimes can be noisy across reclones / CI — when in doubt, ask.

## Output expectations

After a successful run, report briefly:

```
Daemonstrate: first run
- Detected stack: Node/Express 5, React 19, Postgres 16, Expo mobile
- Layers: Frontend, Mobile, Backend, Data, Jobs, Integrations, Infra
- Portfolio: docs/architecture-portfolio.drawio (7 lanes, 23 nodes)
- Detailed:  docs/architecture-detailed.drawio (7 lanes, 68 nodes)
- State:     docs/.daemonstrate-state.json
```

For incremental:

```
Daemonstrate: incremental update
- Changed since 7ec88ef: Frontend (4 files), Backend (2 files)
- Diagrams updated. Other layers untouched.
```

## References

- `references/drawio-format.md` — minimal XML cheatsheet + copy-paste swimlane/node/edge fragments
- `references/dark-theme-palette.md` — the palette + per-layer color assignments
- `references/layer-schema.md` — subagent return JSON schema

## Scripts

- `scripts/drawio_builder.py` — graph spec JSON → two `.drawio` files
- `scripts/install-hooks.sh` — installs the post-commit hook in the current repo
- `scripts/post-commit.sh` — the hook body (copied into `.git/hooks/post-commit`)
