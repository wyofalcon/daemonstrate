# Dark Theme Palette

Catppuccin-Mocha-inspired palette, tuned for readable diagrams on GitHub's dark mode and direct `.drawio` viewing.

## Base colors

| Role | Hex | Use |
|---|---|---|
| Canvas background | `#1E1E2E` | `mxGraphModel background`, node fill |
| Lane background | `#2D2D3A` | Swimlane `fillColor` |
| Muted text | `#9399B2` | File paths, subtitles, edge labels |
| Primary text | `#CDD6F4` | Node labels, lane titles |
| Edge default | `#9399B2` | Edge `strokeColor` when unlabeled |
| Edge emphasis | `#F5E0DC` | For "hot path" flows you want to highlight |

## Per-layer accent colors

Assign these **in order of appearance** (first layer detected gets the first color). If a repo has a layer not in the standard vocab, use `#94E2D5` (teal) as overflow.

| Layer | Accent | Rationale |
|---|---|---|
| Frontend | `#89B4FA` (sky blue) | Client-side / visual |
| Mobile | `#B4BEFE` (periwinkle) | Adjacent to frontend but distinct |
| Backend / API | `#A6E3A1` (mint green) | Server, go-ahead signal |
| Data | `#F9E2AF` (warm yellow) | Storage, cautionary stability |
| Jobs / Workers | `#FAB387` (peach) | Background processes |
| Integrations | `#F38BA8` (rose) | External = warmth/risk |
| Infra | `#CBA6F7` (lavender) | DevOps, abstract/cloud |
| Docs / Assets | `#94E2D5` (teal) | Rarely shown |
| Overflow | `#94E2D5` (teal) | For uncommon layers |

## Contrast rules

- Node fill = canvas (`#1E1E2E`), stroke = layer accent → node "pops" against its lane.
- Lane stroke = layer accent, fill = lane bg → lanes distinguishable from each other.
- Tech badge fill = layer accent, text = canvas (`#1E1E2E`) → high contrast pill.
- Never put white text (`#CDD6F4`) on a yellow or peach fill — use the canvas color for text-on-accent instead.

## What NOT to do

- Don't use more than **3 accent colors** on a single edge or node. Discipline the palette.
- Don't introduce colors outside this table — consistency across both diagrams is how readers map between them.
- Don't use pure black or pure white. The palette is deliberately soft to avoid eye strain.
