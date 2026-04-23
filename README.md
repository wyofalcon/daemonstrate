# Daemonstrate

A [Claude Code](https://claude.ai/code) skill that generates polished, light-theme `.drawio` architecture diagrams for any codebase — and keeps them current via an optional post-commit hook.

```
/daemonstrate
```

---

## What it produces

| File | Pages | Audience | Contents |
|---|---|---|---|
| `docs/architecture-portfolio.drawio` | 1 | Recruiters, stakeholders | Single-page poster. Dashed pastel container per layer with capability pills + tech badges. Headline data flows. Scannable in ~10 seconds. |
| `docs/architecture-detailed.drawio` | 1 + N | Collaborators, AI agents | Multi-page drill-down. Overview page (lane headers + tech badges + headline node teasers) + one detail page per layer (full key-nodes grid + internal edges + clickable "Connects to" sidebar). |
| `docs/architecture-journey.drawio` *(opt-in)* | 1 | Family, non-technical reviewers, end users | Single-page vertical user-flow spine. User actions on the left, app actions on the right, numbered badges down the middle. Hover any step for the rich detail (description / what you'll see / tips). |

All three diagrams use the same visual language — dashed pastel group containers, orthogonal labeled edges, dark text on white, drop shadows. Modeled after a clean architecture flowchart, so a reader switching between them never has to re-orient. GitHub renders `.drawio` files inline when a companion `.svg` export exists.

---

## When is this worth the tokens?

First run on a fresh repo is the expensive one — scope discovery, per-scope exploration, and Plain-English translation of every label all happen once. Incremental runs (driven by the post-commit hook) are much cheaper: three-level caching means most commits only re-explore the scopes whose files changed and re-translate a handful of labels.

The cost earns its keep when:

- **You're onboarding a collaborator.** Drop them into `architecture-detailed.drawio` and let the diagram carry the context you'd otherwise spend most of a meeting explaining.
- **You're sharing with a non-technical stakeholder.** The Plain-English tab renders *"the website asks the server to save a note"* instead of `POST /api/notes` — no separate deck to maintain, no translation drift.
- **You think visually.** The diagrams become external working memory; teaching-mode drill-down lets you zoom into whichever part of the system you're currently reasoning about, on demand.

If none of those apply, a one-time hand-drawn diagram is probably the better call. See [ROADMAP.md](./ROADMAP.md) for work in flight around *opportunistic* generation — deferring the expensive passes to session windows where the tokens would otherwise go unused.

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
4. Generate graph spec    Intermediate JSON describing all diagrams
5. Run drawio_builder.py  Emits valid .drawio XML — single-page portfolio,
                          multi-page detailed (overview + 1 page per layer),
                          and (optionally) single-page journey.
6. Write state sidecar    .daemonstrate-state.json tracks lastSha for incremental runs
```

On subsequent runs, only layers whose files changed since `lastSha` are re-explored. The builder preserves node IDs across generations so PR diffs stay minimal.

---

## Customizing with a graph spec

Drop a `docs/graph-spec.json` in your repo to drive the diagrams directly — useful when you want a curated story instead of (or alongside) the auto-detected architecture.

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

### Adding the journey diagram

Add a `user_flow` array (and run with `--out-journey`) to also produce the single-page user-journey spine:

```json
{
  "title": "My Project",
  "subtitle": "One-line pitch",
  "layers": [...],

  "user_flow": [
    {
      "id": "uf-spot",
      "actor": "user",
      "label": "Spot it",
      "detail": "a bug, idea, or design problem",
      "description": "Longer explanation, surfaced as a hover tooltip.",
      "what_you_see": "What the UI looks like at this moment.",
      "tips": ["Tip one", "Tip two"]
    }
  ]
}
```

`actor` is either `"user"` (renders left, sky blue) or `"app"` (renders right, mint green). The rich `description` / `what_you_see` / `tips` fields all merge into the step's hover tooltip so the page stays scannable.

---

## Running the builder standalone

`scripts/drawio_builder.py` has no external dependencies — pure Python 3.8+ stdlib.

```bash
python scripts/drawio_builder.py \
  --spec docs/graph-spec.json \
  --out-portfolio docs/architecture-portfolio.drawio \
  --out-detailed  docs/architecture-detailed.drawio \
  --out-journey   docs/architecture-journey.drawio   # optional
```

Pipe a spec from stdin:

```bash
echo '{"title":"Demo","layers":[...]}' | python scripts/drawio_builder.py \
  --out-portfolio out/portfolio.drawio \
  --out-detailed  out/detailed.drawio
```

---

## Color palette

Catppuccin-inspired accents on a white canvas. Each accent renders as a pastel fill (22% accent + 78% white) for containers and nodes, with the saturated accent for borders, badges, and capability pills.

| Layer | Accent |
|---|---|
| Frontend | `#89B4FA` sky blue |
| Mobile | `#B4BEFE` periwinkle |
| Backend / API | `#A6E3A1` mint |
| Data | `#F9E2AF` warm yellow |
| Jobs / Workers | `#FAB387` peach |
| Integrations | `#F38BA8` rose |
| Infra | `#CBA6F7` lavender |

Full palette + contrast rules in `references/light-theme-palette.md`.

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
