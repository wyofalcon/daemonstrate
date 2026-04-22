# Light Theme Palette

Light-theme palette tuned to match the visual language of `ai-dev-workflow.drawio`: white canvas, dashed pastel group containers, dark text on light backgrounds, drop shadows, orthogonal labeled edges. Reads cleanly in GitHub light mode and on white slide decks.

## Base colors

| Role | Hex | Use |
|---|---|---|
| Canvas background | `#FFFFFF` | `mxGraphModel background` — every page |
| Title text | `#222222` | Diagram + page titles (22pt bold) |
| Subtitle text | `#666666` | Subtitles, file paths under node labels |
| Body text | `#333333` | Node labels, sidebar pill labels |
| Muted text | `#999999` | Hint text, sidebar headers, "+ N more" markers |
| Edge label color | `#555555` | Edge label text |
| Edge label background | `#FFFFFF` | Background behind edge labels (so they read over routed lines) |
| Default edge stroke | `#999999` | Edge `strokeColor` when no source-layer accent applies |
| Nav background | `#F5F5F5` | "← Back" buttons on detail pages |

The skill never uses pure black or pure white as a foreground/background pair — `#222222` on `#FFFFFF` is the strongest contrast pairing it draws.

## Per-layer accent colors

Assign these **in order of appearance** (first layer detected gets the first color). If a repo has a layer not in the standard vocab, fall through to teal as overflow.

| Layer | Accent | Rationale |
|---|---|---|
| Frontend | `#89B4FA` (sky blue) | Client-side / visual |
| Mobile | `#B4BEFE` (periwinkle) | Adjacent to frontend, distinct |
| Backend / API | `#A6E3A1` (mint green) | Server, go-ahead signal |
| Data | `#F9E2AF` (warm yellow) | Storage, cautionary stability |
| Jobs / Workers | `#FAB387` (peach) | Background processes |
| Integrations | `#F38BA8` (rose) | External = warmth/risk |
| Infra | `#CBA6F7` (lavender) | DevOps, abstract/cloud |
| Docs / Assets | `#94E2D5` (teal) | Rarely shown |
| Overflow | `#94E2D5` (teal) | For uncommon layers |

These hexes are unchanged from v1 — they just play different roles now (fill blends instead of fill solid).

## How accents render

Each accent feeds three derived tones, computed in `drawio_builder.py`:

| Derived | Computation | Used for |
|---|---|---|
| Pastel fill | `light_fill(accent)` — blend 22% accent + 78% white | Group container fill, node fill, sidebar pill fill |
| Solid pill | accent itself | Tech badge fill, capability pill fill (with white text) |
| Stroke | accent itself | Group container border, node border, edge color when source layer is known |

So a `#89B4FA` (sky blue) frontend layer renders as: `#E5EEFD` group fill + `#89B4FA` border + `#89B4FA` solid badges with white text inside.

## Contrast rules

- **Group container = pastel fill + accent border** (matches the "ARCHITECT", "BUILDER" style in ai-dev-workflow.drawio).
- **Standard node = pastel fill + accent border + dark body text** (`#333333`). The pastel fill keeps the node visually grouped with its container while the dark text stays readable.
- **Tech badge = solid accent fill + white text**. High-contrast pill against the pastel container.
- **Capability pill (portfolio only) = solid accent fill + white text**, scaled larger than tech badges.
- **Edge label = `#555555` text on `#FFFFFF` background pill**, so it reads when routed across a busy area.
- Never put white text on yellow (`#F9E2AF`) or peach (`#FAB387`) at small sizes — those accents are too pale for white. The builder uses fontSize=9 bold for tech badges, which is the size where this matters most; if you ever introduce a paler accent, switch its badges to dark text.

## Cross-diagram consistency

All three outputs use this same palette so a reader switching between portfolio → detailed → journey never has to remap colors:

- Portfolio's frontend container, detailed's frontend overview card, and detailed's frontend detail page all share `#89B4FA`.
- Journey only uses two layer accents — sky blue (`#89B4FA`) for user actions and mint green (`#A6E3A1`) for app actions. This visually echoes the frontend ↔ backend split in the architecture diagrams without requiring the reader to know that.

## What NOT to do

- Don't use more than **3 accent colors** on a single edge or node. Discipline the palette.
- Don't introduce colors outside this table — consistency across diagrams is how readers map between them.
- Don't darken the canvas. The visual language depends on white background + pastel fills + dark text. Going dark breaks the ai-dev-workflow aesthetic this skill is modeled on.
- Don't use the layer-accent palette for journey actor colors. Journey uses fixed sky blue / mint green to keep the user/app distinction unambiguous.
