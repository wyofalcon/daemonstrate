# Draw.io XML Format — Minimal Cheatsheet

`.drawio` files are XML describing `mxGraphModel` nodes. The builder handles most of this, but here's the shape for reference / debugging.

## File skeleton (single-page)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="app.diagrams.net" modified="2026-04-22T00:00:00.000Z" agent="daemonstrate" version="24.0.0">
  <diagram name="Architecture" id="main">
    <mxGraphModel dx="1200" dy="800" grid="1" gridSize="10" guides="1" tooltips="1" connect="0"
                  arrows="0" fold="0" page="1" pageScale="1" pageWidth="1600" pageHeight="1000"
                  math="0" shadow="0" background="#FFFFFF">
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />
        <!-- content cells go here -->
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
```

Cells `0` and `1` are mandatory roots — every other cell hangs off `1` as its parent (or off a group container's id for nested content).

## Multi-page file (used by detailed)

Wrap multiple `<diagram>` elements inside one `<mxfile>`. The first one is the default page; subsequent pages are reachable via cell links:

```xml
<mxfile host="app.diagrams.net" modified="..." agent="daemonstrate" version="24.0.0">
  <diagram name="Architecture Overview" id="detailed-overview"> ... </diagram>
  <diagram name="Layer: Frontend" id="layer-frontend"> ... </diagram>
  <diagram name="Layer: Backend" id="layer-backend"> ... </diagram>
</mxfile>
```

To make a cell link to another page, add a `link` attribute with the special `data:page/id,...` form:

```xml
<mxCell id="ovr-frontend"
        value="FRONTEND"
        style="..."
        link="data:page/id,layer-frontend"
        vertex="1" parent="1">
  <mxGeometry x="40" y="120" width="1520" height="130" as="geometry" />
</mxCell>
```

Click handling and back-navigation is built into draw.io / diagrams.net automatically.

## Group container (layer)

Dashed pastel rectangle, full width, one per layer (light-theme — pastel fill + accent border):

```xml
<mxCell id="grp-frontend"
        value="FRONTEND"
        style="rounded=1;whiteSpace=wrap;html=1;shadow=1;fillColor=#E5EEFD;strokeColor=#89B4FA;strokeWidth=2;dashed=1;dashPattern=8 4;verticalAlign=top;align=left;spacingLeft=12;spacingTop=8;fontColor=#89B4FA;fontSize=13;fontStyle=1;"
        vertex="1" parent="1">
  <mxGeometry x="40" y="110" width="1520" height="290" as="geometry" />
</mxCell>
```

The container's `value` is the layer title — rendered top-left inside the box thanks to `verticalAlign=top;align=left;spacingLeft=12;spacingTop=8;`. The dashed `dashPattern=8 4` matches the ai-dev-workflow flowchart aesthetic.

## Node (inside a group container)

Rounded rectangle with pastel fill, accent border, dark body text. Parent is the group container's id, so geometry is relative to the container:

```xml
<mxCell id="fe-app"
        value="&lt;b&gt;App Shell&lt;/b&gt;&lt;br&gt;&lt;font size=&quot;1&quot; color=&quot;#666666&quot;&gt;client/src/App.jsx&lt;/font&gt;"
        style="rounded=1;whiteSpace=wrap;html=1;arcSize=8;shadow=1;fillColor=#E5EEFD;strokeColor=#89B4FA;strokeWidth=1.5;fontColor=#333333;fontSize=11;"
        vertex="1" parent="grp-frontend">
  <mxGeometry x="14" y="68" width="200" height="62" as="geometry" />
</mxCell>
```

HTML in `value` lets you put bold labels + small-grey file paths. Remember to HTML-encode `<`, `>`, `&`, `"` as `&lt;`, `&gt;`, `&amp;`, `&quot;`.

## Tech badge (small pill)

Solid accent fill + white text. Parent is the container so it sits inside the layer:

```xml
<mxCell id="badge-react"
        value="React 19"
        style="rounded=1;whiteSpace=wrap;html=1;arcSize=40;fillColor=#89B4FA;strokeColor=none;fontColor=#FFFFFF;fontSize=9;fontStyle=1;spacingLeft=5;spacingRight=5;"
        vertex="1" parent="grp-frontend">
  <mxGeometry x="14" y="38" width="80" height="22" as="geometry" />
</mxCell>
```

Place tech badges in the title-area row (`y` between container's `spacingTop` end and the first node row).

## Capability pill (portfolio only)

Bigger version of the tech badge, used in the portfolio diagram instead of `key_nodes`:

```xml
<mxCell id="cap-oauth"
        value="Google OAuth + cookie auth"
        style="rounded=1;whiteSpace=wrap;html=1;arcSize=12;shadow=1;fillColor=#89B4FA;strokeColor=none;fontColor=#FFFFFF;fontSize=12;fontStyle=1;spacingLeft=10;spacingRight=10;"
        vertex="1" parent="grp-frontend">
  <mxGeometry x="14" y="72" width="280" height="46" as="geometry" />
</mxCell>
```

## Edge (between nodes or containers)

Orthogonal routed, with a label sitting in a white pill so it reads over routed lines:

```xml
<mxCell id="edge-fe-be"
        value="GET /api/auth/me"
        style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;strokeColor=#89B4FA;strokeWidth=1.5;fontColor=#555555;fontSize=10;labelBackgroundColor=#FFFFFF;"
        edge="1" parent="1" source="fe-app" target="be-routes">
  <mxGeometry relative="1" as="geometry" />
</mxCell>
```

Edges live on `parent="1"` (top-level), not inside containers, even when they connect nodes across containers. The exit/entry pin coordinates (`exitX/Y`, `entryX/Y`) make the edge attach cleanly to the bottom-center of the source and top-center of the target — important when a layer sits above its target layer.

Use the source layer's accent for the `strokeColor` so a reader can trace where each edge originates.

## Nav button (back link on detail pages)

```xml
<mxCell id="nav-back"
        value="← Architecture Overview"
        style="rounded=1;whiteSpace=wrap;html=1;arcSize=40;shadow=1;fillColor=#F5F5F5;strokeColor=#999999;strokeWidth=1;fontColor=#333333;fontSize=11;"
        link="data:page/id,detailed-overview"
        vertex="1" parent="1">
  <mxGeometry x="40" y="20" width="210" height="30" as="geometry" />
</mxCell>
```

## Tooltip on a cell

Add a `tooltip="..."` attribute to surface long-form info on hover (used heavily on the journey diagram so steps stay terse but rich):

```xml
<mxCell id="step-1"
        value="&lt;b&gt;Sign in&lt;/b&gt;"
        tooltip="Google or email — takes 10 seconds. After signing in, you land on your dashboard."
        style="..."
        vertex="1" parent="1">
  <mxGeometry x="60" y="200" width="680" height="80" as="geometry" />
</mxCell>
```

## Layout hints

- **Page size**: `pageWidth="1600"` for all three diagrams. Heights vary based on content (layer count for portfolio/detailed, step count for journey).
- **Container heights**: 180 for portfolio (badges + 1–2 capability pill rows), 130 for the detailed overview (badges + 3 teasers), ~280–600 for detailed per-layer pages (full key_nodes grid).
- **Container y-stride**: `topMargin + layerIndex * (containerHeight + 24)` for vertical spacing.
- **Node grid inside a container**: 4–5 columns × variable rows. Node size 200–220 × 62–70 with 16–18px gutter.
- **Background**: always `#FFFFFF` (white).

## Don'ts

- Don't use raw newlines in `value="..."` — use `&#10;` or `<br>`.
- Don't forget to deduplicate cell IDs — duplicates silently break rendering.
- Don't set `collapsible="1"` on containers for the portfolio (recruiters won't click to expand).
- Don't darken the canvas — the visual language depends on white background + pastel pastels + dark text.
- Don't put nodes inside the container's title-bar zone (`y < 38`) — that's reserved for tech badges.
