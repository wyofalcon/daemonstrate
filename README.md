# Daemonstrate

A [Claude Code](https://claude.ai/code) skill that generates two polished, dark-themed `.drawio` architecture diagrams for any codebase — and keeps them current via an optional post-commit hook.

```
/daemonstrate
```

---

## What it produces

| File | Audience | Contents |
|---|---|---|
| `docs/architecture-portfolio.drawio` | Recruiters, stakeholders | Swimlanes, tech badges, capability pills, headline data flows. Scannable in ~10 seconds. |
| `docs/architecture-detailed.drawio` | Collaborators, AI agents | Routes, services, tables, jobs, integrations, cross-layer edges with labels. |

For projects with a `user_flow` / `phases` spec, the portfolio becomes a **multi-page interactive flow**: an overview → phase pages → step detail pages, each with clickable navigation.

Both diagrams share the same swimlane skeleton and color palette so readers can switch between them without getting lost. GitHub renders `.drawio` files inline when a companion `.svg` export exists.

---

## Installation

Daemonstrate is a Claude Code skill. Clone this repo into your skills directory:

```bash
# Claude Code looks for skills in ~/.claude/skills/ by default
git clone https://github.com/wyofalcon/daemonstrate ~/.claude/skills/daemonstrate
```

Then in Claude Code, invoke it:

```
/daemonstrate
```

That's it. Claude will detect your stack, classify layers, explore the codebase, and write both diagrams into `docs/`.

---

## How it works

```
1. Detect tech stack      package.json, pyproject.toml, go.mod, Cargo.toml, …
2. Classify layers        Frontend / Mobile / Backend / Data / Jobs / Integrations / Infra
3. Explore each layer     Glob + Grep to find routes, services, tables, jobs
4. Generate graph spec    Intermediate JSON describing both diagrams
5. Run drawio_builder.py  Emits valid .drawio XML for portfolio + detailed
6. Write state sidecar    .daemonstrate-state.json tracks lastSha for incremental runs
```

On subsequent runs, only layers whose files changed since `lastSha` are re-explored. The builder preserves node IDs across generations so PR diffs stay minimal.

---

## Customizing with a graph spec

Drop a `docs/graph-spec.json` in your repo to drive the diagrams directly — useful when you want a curated user journey instead of (or alongside) the auto-detected architecture.

### Minimal spec

```json
{
  "title": "My Project",
  "subtitle": "One-line pitch",
  "layers": [
    {
      "layer_name": "backend",
      "display_name": "Backend",
      "accent": "#A6E3A1",
      "tech_badges": ["Node.js", "Express 5"],
      "capabilities": ["REST API", "Auth middleware"],
      "key_nodes": [
        { "id": "be-routes", "label": "POST /api/notes", "file_path": "src/routes/notes.js" }
      ],
      "internal_edges": [],
      "external_edges": []
    }
  ]
}
```

### User-journey spec (portfolio only)

Add `user_flow` and `phases` to get the multi-page interactive flow:

```json
{
  "title": "My Project",
  "subtitle": "One-line pitch",
  "phases": [
    {
      "id": "capture",
      "label": "Capture",
      "tagline": "Grab it before you forget",
      "accent": "#89B4FA",
      "step_ids": ["uf-spot", "uf-hotkey", "uf-popup"]
    }
  ],
  "user_flow": [
    {
      "id": "uf-spot",
      "actor": "user",
      "label": "You spot something worth capturing",
      "detail": "a bug, idea, or design problem",
      "description": "Longer description shown on the step detail page.",
      "what_you_see": "What the UI looks like at this moment.",
      "tips": ["Tip one", "Tip two"]
    }
  ]
}
```

`actor` is either `"user"` (blue) or `"app"` (green). Steps link to each other and back to their phase automatically.

---

## Running the builder standalone

`scripts/drawio_builder.py` has no external dependencies — pure Python 3.8+ stdlib.

```bash
python scripts/drawio_builder.py \
  --spec docs/graph-spec.json \
  --out-portfolio docs/architecture-portfolio.drawio \
  --out-detailed  docs/architecture-detailed.drawio
```

Pipe a spec from stdin:

```bash
echo '{"title":"Demo","layers":[...]}' | python scripts/drawio_builder.py \
  --out-portfolio out/portfolio.drawio \
  --out-detailed  out/detailed.drawio
```

---

## Color palette

Catppuccin-Mocha-inspired, tuned for readability in GitHub dark mode and diagrams.net.

| Layer | Accent |
|---|---|
| Frontend | `#89B4FA` sky blue |
| Mobile | `#B4BEFE` periwinkle |
| Backend / API | `#A6E3A1` mint |
| Data | `#F9E2AF` warm yellow |
| Jobs / Workers | `#FAB387` peach |
| Integrations | `#F38BA8` rose |
| Infra | `#CBA6F7` lavender |

---

## Post-commit hook

During an interactive run, Daemonstrate will offer to install a post-commit hook that re-runs in incremental mode after each commit. Cost per commit is low — only changed layers are re-explored.

To install manually:

```bash
bash scripts/install-hooks.sh /path/to/your/repo
```

---

## Requirements

- **Claude Code** (for the `/daemonstrate` skill invocation)
- **Python 3.8+** (stdlib only, for `drawio_builder.py`)
- **diagrams.net** / **draw.io desktop** to view and edit the output

---

## License

MIT
