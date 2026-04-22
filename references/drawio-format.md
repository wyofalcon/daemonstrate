# Draw.io XML Format — Minimal Cheatsheet

`.drawio` files are XML describing `mxGraphModel` nodes. The builder handles most of this, but here's the shape for reference / debugging.

## File skeleton

```xml
<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="app.diagrams.net" modified="2026-04-19T00:00:00.000Z" agent="daemonstrate" version="24.0.0">
  <diagram name="Architecture" id="main">
    <mxGraphModel dx="1200" dy="800" grid="1" gridSize="10" guides="1" tooltips="1" connect="1"
                  arrows="1" fold="1" page="1" pageScale="1" pageWidth="1600" pageHeight="1000"
                  math="0" shadow="0" background="#1E1E2E">
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />
        <!-- content cells go here -->
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
```

Cells `0` and `1` are mandatory roots — every other cell hangs off `1` as its parent (or off a swimlane's id for nested content).

## Swimlane (layer container)

Horizontal swimlane, full width, one per layer:

```xml
<mxCell id="lane-frontend"
        value="FRONTEND"
        style="swimlane;horizontal=0;startSize=36;fillColor=#2D2D3A;strokeColor=#89B4FA;strokeWidth=2;fontColor=#CDD6F4;fontStyle=1;fontSize=14;rounded=1;arcSize=8;swimlaneFillColor=#1E1E2E;"
        vertex="1" parent="1">
  <mxGeometry x="40" y="40" width="1520" height="140" as="geometry" />
</mxCell>
```

`horizontal=0` makes the title bar appear on the *left* (vertical text), which works well for horizontal lanes stacked vertically. Use `horizontal=1` if you prefer title on top.

## Node (inside a swimlane)

Rounded rectangle. Parent is the swimlane id, so geometry is relative to lane:

```xml
<mxCell id="node-spa"
        value="&lt;b&gt;React SPA&lt;/b&gt;&lt;br&gt;&lt;font size=&quot;1&quot; color=&quot;#9399B2&quot;&gt;client/src/&lt;/font&gt;"
        style="rounded=1;whiteSpace=wrap;html=1;fillColor=#1E1E2E;strokeColor=#89B4FA;fontColor=#CDD6F4;fontSize=12;arcSize=12;shadow=0;"
        vertex="1" parent="lane-frontend">
  <mxGeometry x="60" y="60" width="160" height="60" as="geometry" />
</mxCell>
```

HTML in `value` lets you put bold labels + small-grey file paths. Remember to HTML-encode `<`, `>`, `&`, `"` as `&lt;`, `&gt;`, `&amp;`, `&quot;`.

## Tech badge (small pill)

```xml
<mxCell id="badge-react"
        value="React 19"
        style="rounded=1;fillColor=#89B4FA;strokeColor=none;fontColor=#1E1E2E;fontSize=10;fontStyle=1;arcSize=40;spacingLeft=8;spacingRight=8;"
        vertex="1" parent="lane-frontend">
  <mxGeometry x="800" y="8" width="80" height="20" as="geometry" />
</mxCell>
```

Rest inside the lane's title area (`y < startSize`).

## Edge (between nodes)

```xml
<mxCell id="edge-spa-api"
        value="apiFetch / cookies"
        style="endArrow=classic;html=1;strokeColor=#9399B2;strokeWidth=1.5;fontColor=#CDD6F4;fontSize=10;labelBackgroundColor=#1E1E2E;rounded=0;"
        edge="1" parent="1" source="node-spa" target="node-api">
  <mxGeometry relative="1" as="geometry" />
</mxCell>
```

Edges live on `parent="1"` (top-level), not inside swimlanes, even when they connect nodes across lanes.

## Layout hints

- **Page size**: `pageWidth="1600" pageHeight="1000"` for portfolio; bigger (`2400 x 1600`) for detailed.
- **Lane height**: 140 for portfolio (3-6 nodes, comfortable), 220-280 for detailed (6-12 nodes).
- **Lane y-stride**: `layerIndex * (laneHeight + 24)` for vertical spacing.
- **Node grid inside lane**: 4 columns × 2 rows works for most lanes. Node size 160×60 with 24px gutter.
- **Background**: always `#1E1E2E`.

## Don'ts

- Don't use raw newlines in `value="..."` — use `&#10;` or `<br>`.
- Don't forget to increment cell IDs — duplicates silently break rendering.
- Don't set `collapsible="1"` on swimlanes for the portfolio (recruiters won't click to expand).
