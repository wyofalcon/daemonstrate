---
name: daemonstrate
description: Generates and maintains up to three light-theme `.drawio` architecture diagrams for ANY project, all in the visual language of a flowchart with dashed pastel group containers and orthogonal routed edges — a single-page portfolio poster (for recruiters), a multi-page architecture deep-dive with one drill-down page per layer (for collaborators, returning owners, AI onboarding), and an optional single-page user-journey flow (for non-technical audiences). Diff-based incremental updates keep token cost low after the first pass. Trigger this skill whenever the user asks to visualize, diagram, map, chart, or document their project architecture; wants to onboard a recruiter/collaborator/new teammate; mentions their diagrams are stale or missing; mentions draw.io / flowcharts / architecture diagrams; or when no `docs/architecture-portfolio.drawio` + `docs/architecture-detailed.drawio` pair exists in the current repo and the user is working on documentation, onboarding, portfolio, or repo cleanup tasks. Also trigger on explicit phrases like "Daemonstrate", "refresh the architecture diagrams", or "show what this project does".
---

# Daemonstrate

Produces two (or three) light-theme `.drawio` diagrams for the **target repo** (resolved below). All three share one visual language — dashed pastel group containers, orthogonal routed edges, dark text on white, drop shadows — modeled after a clean architecture flowchart so a reader can move between them without re-orienting.

By default they live under `docs/` in the target repo:

- **`docs/architecture-portfolio.drawio`** — **single-page** poster, scannable in 10 seconds. For recruiters, portfolios, and "what does this project do" introductions. Each layer is a dashed pastel container with 3–6 capability pills + a tech-badge row. Cross-layer edges show headline data flows.
- **`docs/architecture-detailed.drawio`** — **multi-page** drill-down. The first page is a thin overview (layer headers, tech badges, headline component teasers, cross-layer edges); each subsequent page is one layer's deep dive with the full key-nodes grid, internal edges, and a "Connects to" sidebar with clickable pills jumping to other layer pages. Returning collaborators (and AI agents) can iterate through every layer page-by-page without reading the codebase.
- **`docs/architecture-journey.drawio`** *(optional, opt-in)* — **single-page** vertical user-flow spine for **non-technical** audiences (family, recruiters who don't read code, end users). User actions on the left, app actions on the right, numbered badges on a central spine. Rich step detail (description / what_you_see / tips) is delivered as hover tooltips so the page stays scannable. Generated only when the spec includes `user_flow` *and* the builder is run with `--out-journey`.

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

## Why three diagrams, and why draw.io

A single diagram that tries to show every audience ends up illegible to all of them. The split is by **viewer**, not by content overlap:

- **Portfolio** = single-page poster. Recruiter spends < 15 seconds. Capabilities, not files.
- **Detailed** = multi-page deep dive. Collaborator (or AI) opens the overview, picks a layer, drills in. Each page is bounded; total information is unbounded.
- **Journey** = single-page user-facing flow. Non-technical audience. Pure user actions and app responses, zero backend jargon.

All three share the same visual language (dashed pastel group containers, orthogonal labeled edges, per-layer accent colors) so a reader can move between them without re-orienting.

Draw.io (`.drawio` XML) is chosen because: (1) GitHub renders it inline when the companion `.svg` export exists, (2) the XML is text-diffable (reviewable in PRs), (3) users can open and hand-edit in diagrams.net without new tooling, (4) draw.io supports multi-page files with cross-page links — used by the detailed diagram for overview ↔ layer-page navigation. The state sidecar `.daemonstrate-state.json` tracks which files fed into which layer so the *next* run only re-examines changed layers.

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

Not every project has every layer. Omit empty ones. If a project only has one layer, still render a group container for it — a single bounded container is clearer than a free-floating set of nodes.

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


### Step 4 — Generate the diagrams

Read `references/drawio-format.md` (XML structure, group pattern) and `references/light-theme-palette.md` (colors) once.

Assemble a single **graph spec** (JSON) describing all diagrams' content, then pipe it to `scripts/drawio_builder.py` which emits valid `.drawio` XML for each. **Do not hand-write the full XML** — it's repetitive and error-prone; the builder handles IDs, layout math, multi-page wiring, and style strings.

Run the builder (resolve the script path from `$SKILL_DIR`, not a hardcoded absolute):

```bash
python "$SKILL_DIR/scripts/drawio_builder.py" \
  --spec graph-spec.json \
  --out-portfolio "$OUT_DIR/architecture-portfolio.drawio" \
  --out-detailed "$OUT_DIR/architecture-detailed.drawio" \
  [--out-journey "$OUT_DIR/architecture-journey.drawio"]
```

`--out-journey` is opt-in. Add it (and a `user_flow` section to the spec — see below) when the user asks for a non-technical, "show my grandma" or "recruiter-first" walkthrough.

#### Journey spec (when `--out-journey` is used)

Add a top-level `user_flow` array to `graph-spec.json` alongside `layers`:

```json
{
  "title": "...",
  "subtitle": "...",
  "layers": [...],

  "user_flow": [
    {
      "id": "s1",
      "actor": "user",
      "label": "Sign in",
      "detail": "Google or email — takes 10 seconds",
      "description": "Friendly 1–3 sentence explanation of what happens on this step.",
      "what_you_see": "A short sentence describing the visual cue (button, screen, animation).",
      "tips": ["Optional plain-language tip 1", "Optional tip 2"]
    }
  ]
}
```

- `user_flow`: ordered list of steps rendered top-to-bottom along a central spine. `actor` is `"user"` (renders on the left in sky blue) or `"app"` (renders on the right in mint green). Keep `label` ≤4 words and `detail` ≤8 words — they're shown directly on the step box.
- `description`, `what_you_see`, and `tips` are merged into the step's hover tooltip, which keeps the page scannable while preserving the rich storytelling content.
- A `phases` key is accepted but ignored in the single-page layout (kept for spec compatibility with older runs).

Resolve the Python binary portably:
- Unix/macOS: `command -v python3 || command -v python`
- Windows (Git Bash): `command -v python` (both `python` and `py -3` work); or `where python` in CMD/PowerShell.
- Minimum: Python 3.8 with stdlib only. The builder has no external dependencies.

If no Python is available at all, fall through and hand-write the XML using `references/drawio-format.md` — slower and more error-prone, but workable.

**Portfolio content rules (single-page poster):**
- Header: project name + one-line pitch (pulled from README H1 + first paragraph, or `package.json` `description`).
- One dashed pastel container per layer, stacked vertically.
- Inside each container: 3-6 **capability pills** (not file names). Examples: "Google OAuth + cookie auth", "SMS intake via Twilio", "Offline SQLite + delta sync".
- Tech badge row along each container's top edge.
- 4-8 cross-layer edges showing the headline data flows (label them: "JWT cookie", "REST /api", "SMS webhook", etc.).
- Leave whitespace. A recruiter spends under 15 seconds.

**Detailed content rules (multi-page drill-down):**
- The builder produces **one overview page + one detail page per layer**. The overview is intentionally thin: layer headers, tech badges, 3 headline node teasers, "View N components →" CTA, plus cross-layer edges. Each layer container on the overview is clickable and links to its detail page.
- Each layer detail page shows: the full `key_nodes` grid (4–5 columns wide), all internal edges between those nodes, and a **"Connects to" sidebar** on the right with clickable pills for each linked layer (jumps to that layer's page).
- File paths render below node labels in smaller text. Hover any node for the long-form `detail`.
- Edges labeled with *what* flows (HTTP verb + path, event name, DB table).
- Include Jobs/Workers and Integrations lanes even if small — that's where collaborators get surprised.
- The overview and per-layer pages share IDs and palette so a reader switching back and forth never loses orientation.

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

- `references/drawio-format.md` — minimal XML cheatsheet + copy-paste group-container/node/edge fragments + multi-page link syntax
- `references/light-theme-palette.md` — the palette + per-layer accent assignments
- `references/layer-schema.md` — subagent return JSON schema

## Scripts

- `scripts/drawio_builder.py` — graph spec JSON → 2 or 3 `.drawio` files (portfolio single-page, detailed multi-page, journey single-page)
- `scripts/install-hooks.sh` — installs the post-commit hook in the current repo
- `scripts/post-commit.sh` — the hook body (copied into `.git/hooks/post-commit`)
