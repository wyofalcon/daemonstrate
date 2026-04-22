# Layer Schema

This is the JSON contract a layer-explorer subagent must return. The main agent merges all layers into a single graph spec and pipes it to `drawio_builder.py`.

## Schema

```json
{
  "layer_name": "frontend",
  "display_name": "Frontend",
  "accent": "#89B4FA",
  "tech_badges": ["React 19", "Vite", "React Router 7"],
  "capabilities": [
    "Google OAuth sign-in",
    "Offline-capable PWA",
    "Real-time note compose",
    "Protected routes via httpOnly cookies"
  ],
  "key_nodes": [
    {
      "id": "fe-app",
      "label": "App Shell",
      "file_path": "client/src/App.jsx",
      "detail": "React Router 7 root"
    },
    {
      "id": "fe-apiclient",
      "label": "apiFetch",
      "file_path": "client/src/api/client.js",
      "detail": "401 auto-refresh"
    }
  ],
  "internal_edges": [
    {"from": "fe-app", "to": "fe-apiclient", "label": ""}
  ],
  "external_edges": [
    {
      "from": "fe-apiclient",
      "to_layer": "backend",
      "to_label_hint": "routes/auth",
      "label": "GET /api/auth/me"
    }
  ]
}
```

## Field-by-field

| Field | Required | Purpose |
|---|---|---|
| `layer_name` | yes | Machine id. Lowercase, no spaces. Used as a prefix for cell IDs. |
| `display_name` | yes | Human-readable title shown on the swimlane. |
| `accent` | yes | Hex from `dark-theme-palette.md`. |
| `tech_badges` | yes | 1-5 short strings. Shown as pills on the lane. |
| `capabilities` | yes | 3-6 **user-facing** capability phrases. These populate the **portfolio** diagram. Keep under 5 words each. |
| `key_nodes` | yes | 6-12 structural nodes for the **detailed** diagram. |
| `internal_edges` | yes (may be empty) | Edges between nodes in *this* layer. |
| `external_edges` | yes (may be empty) | Edges that leave this layer. `to_layer` must match another layer's `layer_name`. `to_label_hint` is used to find the target node by substring match. |

## Node ID conventions

Prefix every `id` with the layer short-code:
- Frontend → `fe-*`
- Mobile → `mo-*`
- Backend → `be-*`
- Data → `da-*`
- Jobs → `jb-*`
- Integrations → `ig-*`
- Infra → `in-*`

This guarantees no ID collisions when layers are merged.

## Stability

When a subagent is given a **previous snapshot** (incremental mode), it should:

1. Preserve existing `id`s for nodes whose concept still exists (even if the label changes).
2. Only coin new IDs for genuinely new nodes.
3. Remove nodes whose concept is gone.

This keeps the `.drawio` XML diffs minimal in PRs.

## Capability phrasing

Good capabilities read like **marketing bullets** — what a user or caller can do. Bad capabilities read like code tour notes.

| Good | Bad |
|---|---|
| "SMS intake via Twilio" | "Twilio webhook handler" |
| "Offline-first sync" | "SQLite local database" |
| "AI-powered categorization" | "Gemini API client" |
| "Google OAuth sign-in" | "Auth middleware" |

## Node phrasing

Nodes are technical. Use the actual identifier or path:

| Good | Bad |
|---|---|
| `POST /api/mobile/sync` | "Sync endpoint" |
| `note-pipeline.js` | "Note processing" |
| `users` table | "User storage" |
