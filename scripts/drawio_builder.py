#!/usr/bin/env python3
"""
drawio_builder.py — Turn a graph spec JSON into draw.io diagrams.

Generates 2 or 3 light-theme `.drawio` files in the visual language of
ai-dev-workflow.drawio: dashed pastel group containers, orthogonal labeled
edges, dark text on light backgrounds, drop shadows.

Outputs:
  - portfolio (single-page poster — capability pills + tech badges)
  - detailed  (multi-page: overview + one drill-down page per layer)
  - journey   (optional, single-page user-flow spine)

Why a script instead of hand-writing XML in the skill:
- Keeps the skill body short (progressive disclosure).
- Guarantees valid XML, unique IDs, consistent geometry math.
- Preserves node IDs across regens so PR diffs stay minimal.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ── Light-theme palette (matches ai-dev-workflow.drawio) ─────────────────────

PALETTE = {
    "canvas":     "#FFFFFF",
    "title":      "#222222",
    "subtitle":   "#666666",
    "body":       "#333333",
    "muted":      "#999999",
    "label":      "#555555",
    "edge":       "#999999",
    "edge_label": "#FFFFFF",
    "nav_bg":     "#F5F5F5",
}

LAYER_SHORT = {
    "frontend": "fe", "mobile": "mo", "backend": "be", "api": "be",
    "data": "da", "jobs": "jb", "workers": "jb", "integrations": "ig",
    "infra": "in", "docs": "dc", "assets": "dc",
}


# ── Tiny utilities ───────────────────────────────────────────────────────────

def esc(s: str) -> str:
    """XML-attribute escape. Use on every user-provided string."""
    return html.escape(s or "", quote=True)


def stable_id(prefix: str, seed: str) -> str:
    """Short deterministic id from a seed string. Stable across regens."""
    h = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:8]
    return f"{prefix}-{h}"


def light_fill(accent: str) -> str:
    """Blend accent 22% toward white — for group/node backgrounds."""
    try:
        r = int(accent[1:3], 16) * 0.22 + 255 * 0.78
        g = int(accent[3:5], 16) * 0.22 + 255 * 0.78
        b = int(accent[5:7], 16) * 0.22 + 255 * 0.78
        return f"#{int(r):02X}{int(g):02X}{int(b):02X}"
    except (ValueError, IndexError):
        return "#F5F5F5"


def darker(accent: str, factor: float = 0.72) -> str:
    """Darken an accent — used for gradient endpoints, hover states."""
    try:
        r = max(0, int(int(accent[1:3], 16) * factor))
        g = max(0, int(int(accent[3:5], 16) * factor))
        b = max(0, int(int(accent[5:7], 16) * factor))
        return f"#{r:02X}{g:02X}{b:02X}"
    except (ValueError, IndexError):
        return "#333333"


def html_label(main: str, sub: str | None = None) -> str:
    """Bold dark main + small muted sub (used inside light-theme nodes)."""
    if sub:
        return (
            f"<b>{esc(main)}</b>"
            f"<br><font size=\"1\" color=\"{PALETTE['subtitle']}\">{esc(sub)}</font>"
        )
    return f"<b>{esc(main)}</b>"


# ── Style helpers (light theme, ai-dev-workflow visual language) ─────────────

def header_style() -> str:
    return (
        f"text;html=1;strokeColor=none;fillColor=none;"
        f"align=left;verticalAlign=middle;"
        f"fontColor={PALETTE['title']};fontSize=22;fontStyle=1;"
    )


def subtitle_style() -> str:
    return (
        f"text;html=1;strokeColor=none;fillColor=none;"
        f"align=left;verticalAlign=middle;"
        f"fontColor={PALETTE['subtitle']};fontSize=12;"
    )


def hint_style() -> str:
    return (
        f"text;html=1;strokeColor=none;fillColor=none;"
        f"align=right;verticalAlign=middle;"
        f"fontColor={PALETTE['muted']};fontSize=11;fontStyle=2;"
    )


def group_container_style(accent: str) -> str:
    """Dashed pastel container — the signature ai-dev-workflow group block."""
    return (
        f"rounded=1;whiteSpace=wrap;html=1;shadow=1;"
        f"fillColor={light_fill(accent)};strokeColor={accent};strokeWidth=2;"
        f"dashed=1;dashPattern=8 4;"
        f"verticalAlign=top;align=left;spacingLeft=12;spacingTop=8;"
        f"fontColor={accent};fontSize=13;fontStyle=1;"
    )


def node_style(accent: str) -> str:
    """Standard light-theme node: pastel fill, accent stroke, dark text."""
    return (
        f"rounded=1;whiteSpace=wrap;html=1;arcSize=8;shadow=1;"
        f"fillColor={light_fill(accent)};strokeColor={accent};strokeWidth=1.5;"
        f"fontColor={PALETTE['body']};fontSize=11;"
    )


def capability_style(accent: str) -> str:
    """Solid-fill pastel pill for portfolio capability statements."""
    return (
        f"rounded=1;whiteSpace=wrap;html=1;arcSize=12;shadow=1;"
        f"fillColor={accent};strokeColor=none;"
        f"fontColor=#FFFFFF;fontSize=12;fontStyle=1;"
        f"spacingLeft=10;spacingRight=10;"
    )


def badge_style(accent: str) -> str:
    """Small tech badge pill (top of group containers)."""
    return (
        f"rounded=1;whiteSpace=wrap;html=1;arcSize=40;"
        f"fillColor={accent};strokeColor=none;"
        f"fontColor=#FFFFFF;fontSize=9;fontStyle=1;"
        f"spacingLeft=5;spacingRight=5;"
    )


def edge_style(color: str | None = None, src_above: bool | None = None,
               dashed: bool = False) -> str:
    """Orthogonal routed edge with optional pin-points."""
    pins = ""
    if src_above is True:
        pins = "exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;"
    elif src_above is False:
        pins = "exitX=0.5;exitY=0;exitDx=0;exitDy=0;entryX=0.5;entryY=1;entryDx=0;entryDy=0;"
    stroke = color or PALETTE["edge"]
    dash_part = "dashed=1;dashPattern=5 5;" if dashed else ""
    return (
        f"edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;{pins}"
        f"strokeColor={stroke};strokeWidth=1.5;{dash_part}"
        f"fontColor={PALETTE['label']};fontSize=10;"
        f"labelBackgroundColor={PALETTE['edge_label']};"
    )


def nav_button_style() -> str:
    """Small rounded button — used for ← Back navigation on detail pages."""
    return (
        f"rounded=1;whiteSpace=wrap;html=1;arcSize=40;shadow=1;"
        f"fillColor={PALETTE['nav_bg']};strokeColor={PALETTE['muted']};strokeWidth=1;"
        f"fontColor={PALETTE['body']};fontSize=11;"
    )


def actor_shape_style(accent: str = "#89B4FA") -> str:
    """Stick-figure actor — for journey persona at the top of the page."""
    return (
        f"shape=actor;whiteSpace=wrap;html=1;"
        f"fillColor={light_fill(accent)};strokeColor={accent};strokeWidth=1.5;"
        f"fontColor={PALETTE['body']};fontSize=11;"
    )


def section_label_style(color: str) -> str:
    """Small bold label for sidebar sections, uses the given color."""
    return (
        f"text;html=1;strokeColor=none;fillColor=none;"
        f"align=left;verticalAlign=top;"
        f"fontColor={color};fontSize=11;fontStyle=1;"
    )


# ── Cell dataclass ───────────────────────────────────────────────────────────

@dataclass
class Cell:
    """One mxCell. Rendered to XML at the end."""
    id: str
    value: str
    style: str
    parent: str
    vertex: bool = False
    edge: bool = False
    source: str | None = None
    target: str | None = None
    x: int = 0
    y: int = 0
    w: int = 0
    h: int = 0
    tooltip: str | None = None   # shown on hover in draw.io
    link: str | None = None      # "data:page/id,<diagram-id>" for page navigation

    def to_xml(self) -> str:
        attrs = [
            f'id="{esc(self.id)}"',
            f'value="{esc(self.value)}"' if self.value else 'value=""',
            f'style="{esc(self.style)}"',
            f'parent="{esc(self.parent)}"',
        ]
        if self.tooltip:
            attrs.append(f'tooltip="{esc(self.tooltip)}"')
        if self.link:
            attrs.append(f'link="{esc(self.link)}"')
        if self.vertex:
            attrs.append('vertex="1"')
        if self.edge:
            attrs.append('edge="1"')
            if self.source:
                attrs.append(f'source="{esc(self.source)}"')
            if self.target:
                attrs.append(f'target="{esc(self.target)}"')

        geom = (
            f'<mxGeometry x="{self.x}" y="{self.y}" width="{self.w}" height="{self.h}" as="geometry" />'
            if self.vertex
            else '<mxGeometry relative="1" as="geometry" />'
        )
        return f"<mxCell {' '.join(attrs)}>{geom}</mxCell>"


# ── Renderers ────────────────────────────────────────────────────────────────

def _diagram_xml(
    cells: list[Cell],
    name: str,
    diagram_id: str,
    page_w: int,
    page_h: int,
    *,
    grid: bool = True,
    background: str | None = None,
) -> str:
    body = "\n        ".join(c.to_xml() for c in cells)
    grid_val = "1" if grid else "0"
    bg = background or PALETTE["canvas"]
    return (
        f'  <diagram name="{esc(name)}" id="{esc(diagram_id)}">\n'
        f'    <mxGraphModel dx="1200" dy="800" grid="{grid_val}" gridSize="10" guides="1" '
        f'tooltips="1" connect="0" arrows="0" fold="0" page="1" pageScale="1" '
        f'pageWidth="{page_w}" pageHeight="{page_h}" math="0" shadow="0" '
        f'background="{bg}">\n'
        f'      <root>\n'
        f'        <mxCell id="0" />\n'
        f'        <mxCell id="1" parent="0" />\n'
        f'        {body}\n'
        f'      </root>\n'
        f'    </mxGraphModel>\n'
        f'  </diagram>'
    )


def render_mxfile(
    cells: list[Cell],
    *,
    name: str,
    page_w: int,
    page_h: int,
    background: str | None = None,
) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<mxfile host="app.diagrams.net" modified="{now}" agent="daemonstrate" version="24.0.0">\n'
        + _diagram_xml(cells, name, name.lower(), page_w, page_h, grid=True, background=background) +
        '\n</mxfile>\n'
    )


def render_mxfile_paged(
    pages: list[tuple[list[Cell], str, str, int, int]],
) -> str:
    """Render multiple pages into a single .drawio file.

    Each entry: (cells, page_name, page_id, page_w, page_h).
    The first page is the default view; subsequent pages are reachable via
    cell link="data:page/id,<page_id>" attributes.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    diagrams = [
        _diagram_xml(cells, name, pid, pw, ph, grid=(i == 0))
        for i, (cells, name, pid, pw, ph) in enumerate(pages)
    ]
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<mxfile host="app.diagrams.net" modified="{now}" agent="daemonstrate" version="24.0.0">\n'
        + '\n'.join(diagrams) +
        '\n</mxfile>\n'
    )


# ── Builder: PORTFOLIO (single-page poster) ──────────────────────────────────

def build_portfolio(spec: dict[str, Any]) -> str:
    """Single-page light-theme portfolio.

    Each layer is a dashed pastel container holding 3-6 capability pills + a
    tech badge row. Cross-layer orthogonal edges show the headline data flows.
    """
    cells: list[Cell] = []
    layers = spec.get("layers", [])

    page_w = 1600
    left_margin = 40
    top_margin = 96
    grp_w = page_w - 2 * left_margin
    grp_h = 180
    grp_gap = 24

    cells.append(Cell(
        id="hdr-title", value=esc(spec.get("title", "Project")),
        style=header_style(), parent="1", vertex=True,
        x=left_margin, y=20, w=grp_w, h=32,
    ))
    if spec.get("subtitle"):
        cells.append(Cell(
            id="hdr-sub", value=esc(spec["subtitle"]),
            style=subtitle_style(), parent="1", vertex=True,
            x=left_margin, y=54, w=grp_w, h=22,
        ))

    grp_ids: dict[str, str] = {}
    idx_by_layer: dict[str, int] = {}
    accent_by_layer: dict[str, str] = {}

    for idx, layer in enumerate(layers):
        grp_y = top_margin + idx * (grp_h + grp_gap)
        grp_id = f"grp-p-{layer['layer_name']}"
        accent = layer["accent"]

        grp_ids[layer["layer_name"]] = grp_id
        idx_by_layer[layer["layer_name"]] = idx
        accent_by_layer[layer["layer_name"]] = accent

        cells.append(Cell(
            id=grp_id, value=esc(layer["display_name"].upper()),
            style=group_container_style(accent),
            parent="1", vertex=True,
            x=left_margin, y=grp_y, w=grp_w, h=grp_h,
        ))

        # Tech badges row
        badge_x = 14
        for btext in layer.get("tech_badges", [])[:7]:
            bw = max(60, 10 + 8 * len(btext))
            cells.append(Cell(
                id=stable_id(f"{grp_id}-badge", btext),
                value=esc(btext),
                style=badge_style(accent),
                parent=grp_id, vertex=True,
                x=badge_x, y=38, w=bw, h=22,
            ))
            badge_x += bw + 8

        # Capability pills (balanced 1-2 row layout)
        caps = layer.get("capabilities", [])[:6]
        cap_w = 280
        cap_h = 46
        cap_gap_x = 24
        cap_gap_y = 14
        if len(caps) <= 4:
            cols = max(1, len(caps))
        else:
            cols = math.ceil(len(caps) / 2)
        start_x = 14
        start_y = 72
        for i, cap in enumerate(caps):
            row, col = divmod(i, cols)
            cells.append(Cell(
                id=stable_id(f"{grp_id}-cap", cap),
                value=esc(cap),
                style=capability_style(accent),
                parent=grp_id, vertex=True,
                x=start_x + col * (cap_w + cap_gap_x),
                y=start_y + row * (cap_h + cap_gap_y),
                w=cap_w, h=cap_h,
            ))

    # Cross-layer edges — group + dedupe + colored by source accent
    edge_groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for layer in layers:
        for ext in layer.get("external_edges", []):
            tgt = ext.get("to_layer", "")
            if tgt not in grp_ids:
                continue
            key = (layer["layer_name"], tgt)
            lbl = ext.get("label", "")
            if lbl:
                edge_groups[key].append(lbl)
            else:
                edge_groups[key]  # ensure key exists

    for (src_layer, tgt_layer), labels in edge_groups.items():
        src_grp = grp_ids[src_layer]
        tgt_grp = grp_ids[tgt_layer]
        merged = " / ".join(dict.fromkeys(labels))
        src_above = idx_by_layer[src_layer] < idx_by_layer[tgt_layer]
        color = accent_by_layer[src_layer]
        eid = stable_id("ep", f"{src_layer}->{tgt_layer}")
        cells.append(Cell(
            id=eid, value=esc(merged),
            style=edge_style(color, src_above),
            parent="1", edge=True,
            source=src_grp, target=tgt_grp,
        ))

    page_h = top_margin + len(layers) * (grp_h + grp_gap) + 40
    return render_mxfile(cells, name="Portfolio", page_w=page_w, page_h=page_h)


# ── Builder: DETAILED (multi-page) ───────────────────────────────────────────

def build_detailed(spec: dict[str, Any]) -> str:
    """Multi-page detailed architecture in the ai-dev-workflow visual language.

    Page 1: Overview — slim layer headers + tech badges + headline node teasers
            + cross-layer edges. Each layer container is clickable.
    Page 2..N: One drill-down page per layer with the full key_nodes grid,
            internal edges, and a "Connects to" sidebar with clickable pills.
    """
    layers = spec.get("layers", [])
    overview_id = "detailed-overview"
    page_id_by_layer = {ln["layer_name"]: f"layer-{ln['layer_name']}" for ln in layers}

    pages = [build_detailed_overview(spec, overview_id, page_id_by_layer)]
    for layer in layers:
        pages.append(build_layer_detail(layer, spec, overview_id, page_id_by_layer))
    return render_mxfile_paged(pages)


def build_detailed_overview(
    spec: dict[str, Any],
    overview_id: str,
    page_id_by_layer: dict[str, str],
) -> tuple[list[Cell], str, str, int, int]:
    """Overview page: thin layer cards (badges + 3 teasers) + cross-layer edges."""
    cells: list[Cell] = []
    layers = spec.get("layers", [])

    page_w = 1600
    left_margin = 40
    top_margin = 110
    grp_w = page_w - 2 * left_margin
    grp_h = 130
    grp_gap = 24

    accent_by_layer = {ln["layer_name"]: ln["accent"] for ln in layers}
    idx_by_layer = {ln["layer_name"]: i for i, ln in enumerate(layers)}
    grp_ids: dict[str, str] = {}

    cells.append(Cell(
        id="hdr-title",
        value=esc(spec.get("title", "Project") + " — Architecture"),
        style=header_style(), parent="1", vertex=True,
        x=left_margin, y=20, w=grp_w, h=32,
    ))
    if spec.get("subtitle"):
        cells.append(Cell(
            id="hdr-sub", value=esc(spec["subtitle"]),
            style=subtitle_style(), parent="1", vertex=True,
            x=left_margin, y=54, w=grp_w, h=22,
        ))
    cells.append(Cell(
        id="hdr-hint", value="Click any layer to drill in",
        style=hint_style(), parent="1", vertex=True,
        x=left_margin, y=78, w=grp_w, h=22,
    ))

    for idx, layer in enumerate(layers):
        grp_y = top_margin + idx * (grp_h + grp_gap)
        grp_id = f"ovr-{layer['layer_name']}"
        grp_ids[layer["layer_name"]] = grp_id
        accent = layer["accent"]

        nodes = layer.get("key_nodes", [])
        int_edges = layer.get("internal_edges", [])
        node_count = len(nodes)

        cells.append(Cell(
            id=grp_id,
            value=esc(layer["display_name"].upper()),
            style=group_container_style(accent),
            parent="1", vertex=True,
            x=left_margin, y=grp_y, w=grp_w, h=grp_h,
            link=f"data:page/id,{page_id_by_layer[layer['layer_name']]}",
            tooltip=f"Drill into {layer['display_name']} — {node_count} components",
        ))

        # CTA in the upper-right of the container header
        if int_edges:
            cta_text = f"View all {node_count} components ({len(int_edges)} connections) →"
        else:
            cta_text = f"View all {node_count} components →"
        cells.append(Cell(
            id=f"{grp_id}-cta", value=esc(cta_text),
            style=(
                f"text;html=1;strokeColor=none;fillColor=none;"
                f"align=right;verticalAlign=middle;"
                f"fontColor={accent};fontSize=11;fontStyle=1;"
            ),
            parent=grp_id, vertex=True,
            x=grp_w - 320, y=8, w=300, h=22,
        ))

        # Tech badges
        badge_x = 14
        for btext in layer.get("tech_badges", [])[:7]:
            bw = max(60, 10 + 8 * len(btext))
            cells.append(Cell(
                id=stable_id(f"{grp_id}-badge", btext),
                value=esc(btext),
                style=badge_style(accent),
                parent=grp_id, vertex=True,
                x=badge_x, y=38, w=bw, h=22,
            ))
            badge_x += bw + 8

        # Headline node teasers (first 3 key_nodes)
        teaser_w = 360
        teaser_h = 42
        teaser_gap = 18
        teaser_y = 70
        for i, node in enumerate(nodes[:3]):
            tid = stable_id(
                f"{grp_id}-teaser",
                node.get("id") or node.get("label", str(i)),
            )
            cells.append(Cell(
                id=tid,
                value=html_label(
                    node.get("label", "?"),
                    node.get("file_path") or node.get("detail"),
                ),
                style=node_style(accent),
                parent=grp_id, vertex=True,
                x=14 + i * (teaser_w + teaser_gap),
                y=teaser_y, w=teaser_w, h=teaser_h,
            ))

        if node_count > 3:
            cells.append(Cell(
                id=f"{grp_id}-more",
                value=esc(f"+ {node_count - 3} more"),
                style=(
                    f"text;html=1;strokeColor=none;fillColor=none;"
                    f"align=left;verticalAlign=middle;"
                    f"fontColor={PALETTE['muted']};fontSize=11;fontStyle=2;"
                ),
                parent=grp_id, vertex=True,
                x=14 + 3 * (teaser_w + teaser_gap),
                y=teaser_y + 10, w=120, h=22,
            ))

    # Cross-layer edges
    edge_groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for layer in layers:
        for ext in layer.get("external_edges", []):
            tgt = ext.get("to_layer", "")
            if tgt not in grp_ids:
                continue
            key = (layer["layer_name"], tgt)
            lbl = ext.get("label", "")
            if lbl:
                edge_groups[key].append(lbl)
            else:
                edge_groups[key]

    for (src_layer, tgt_layer), labels in edge_groups.items():
        merged = " / ".join(dict.fromkeys(labels))
        src_above = idx_by_layer[src_layer] < idx_by_layer[tgt_layer]
        color = accent_by_layer[src_layer]
        eid = stable_id("ovr-e", f"{src_layer}->{tgt_layer}")
        cells.append(Cell(
            id=eid, value=esc(merged),
            style=edge_style(color, src_above),
            parent="1", edge=True,
            source=grp_ids[src_layer], target=grp_ids[tgt_layer],
        ))

    page_h = top_margin + len(layers) * (grp_h + grp_gap) + 40
    return cells, "Architecture Overview", overview_id, page_w, page_h


def build_layer_detail(
    layer: dict,
    spec: dict[str, Any],
    overview_id: str,
    page_id_by_layer: dict[str, str],
) -> tuple[list[Cell], str, str, int, int]:
    """One layer's drill-down page: full key_nodes + internal edges + connects-to sidebar."""
    cells: list[Cell] = []
    accent = layer["accent"]
    layer_name = layer["layer_name"]
    page_id = page_id_by_layer[layer_name]
    layers = spec.get("layers", [])
    accent_by_layer = {ln["layer_name"]: ln["accent"] for ln in layers}

    page_w = 1600
    left_margin = 40
    top_margin = 110
    sidebar_w = 260
    sidebar_gap = 20

    # ── Nav row + title ───────────────────────────────────────
    cells.append(Cell(
        id="nav-back", value="← Architecture Overview",
        style=nav_button_style(), parent="1", vertex=True,
        x=left_margin, y=20, w=210, h=30,
        link=f"data:page/id,{overview_id}",
        tooltip="Back to architecture overview",
    ))
    cells.append(Cell(
        id="layer-title", value=esc(layer["display_name"]),
        style=(
            f"text;html=1;strokeColor=none;fillColor=none;"
            f"align=left;verticalAlign=middle;"
            f"fontColor={accent};fontSize=24;fontStyle=1;"
        ),
        parent="1", vertex=True,
        x=left_margin, y=58, w=900, h=36,
    ))
    nodes = layer.get("key_nodes", [])
    int_edges = layer.get("internal_edges", [])
    ext_edges = layer.get("external_edges", [])
    cells.append(Cell(
        id="layer-meta",
        value=esc(
            f"{len(nodes)} components · {len(int_edges)} internal connections · "
            f"{len(ext_edges)} external"
        ),
        style=subtitle_style(), parent="1", vertex=True,
        x=left_margin, y=92, w=900, h=22,
    ))

    # ── Body container with full key_nodes grid ───────────────
    body_w = page_w - 2 * left_margin - sidebar_w - sidebar_gap
    grp_id = f"grp-{layer_name}"
    body_y = top_margin + 18

    # Pre-compute grid so we can size the container correctly
    node_w = 220
    node_h = 70
    gap_x = 18
    gap_y = 16
    inner_w = body_w - 28  # account for 14px L/R padding
    cols = max(1, (inner_w + gap_x) // (node_w + gap_x))
    start_x = 14
    start_y = 72
    rows = math.ceil(len(nodes) / cols) if nodes else 0
    body_h = max(280, start_y + rows * (node_h + gap_y) + 14)

    cells.append(Cell(
        id=grp_id, value=esc(layer["display_name"].upper()),
        style=group_container_style(accent),
        parent="1", vertex=True,
        x=left_margin, y=body_y, w=body_w, h=body_h,
    ))

    # Tech badges
    badge_x = 14
    for btext in layer.get("tech_badges", [])[:8]:
        bw = max(60, 10 + 8 * len(btext))
        cells.append(Cell(
            id=stable_id(f"{grp_id}-badge", btext),
            value=esc(btext),
            style=badge_style(accent),
            parent=grp_id, vertex=True,
            x=badge_x, y=38, w=bw, h=22,
        ))
        badge_x += bw + 8

    # Key nodes grid
    for i, node in enumerate(nodes):
        row, col = divmod(i, cols)
        nid = node.get("id") or stable_id(f"{grp_id}-n", node.get("label", str(i)))
        tooltip = node.get("detail") or node.get("file_path") or ""
        cells.append(Cell(
            id=nid,
            value=html_label(
                node.get("label", node.get("id", "?")),
                node.get("file_path") or node.get("detail"),
            ),
            style=node_style(accent),
            parent=grp_id, vertex=True,
            x=start_x + col * (node_w + gap_x),
            y=start_y + row * (node_h + gap_y),
            w=node_w, h=node_h,
            tooltip=tooltip if tooltip else None,
        ))

    # Internal edges
    for e in int_edges:
        src = e.get("from")
        tgt = e.get("to")
        if not src or not tgt:
            continue
        eid = stable_id("ie", f"{src}->{tgt}-{e.get('label','')}")
        cells.append(Cell(
            id=eid, value=esc(e.get("label", "")),
            style=edge_style(accent),
            parent="1", edge=True,
            source=src, target=tgt,
        ))

    # ── Sidebar: Connects to ──────────────────────────────────
    sidebar_x = left_margin + body_w + sidebar_gap
    sidebar_y = body_y
    cells.append(Cell(
        id="sb-title", value="<b>CONNECTS TO</b>",
        style=section_label_style(PALETTE["label"]),
        parent="1", vertex=True,
        x=sidebar_x + 6, y=sidebar_y, w=sidebar_w - 12, h=22,
    ))

    out_targets: dict[str, list[str]] = defaultdict(list)
    for ext in ext_edges:
        tgt_layer = ext.get("to_layer", "")
        if tgt_layer in page_id_by_layer:
            lbl = ext.get("label", "")
            if lbl:
                out_targets[tgt_layer].append(lbl)
            else:
                out_targets[tgt_layer]

    in_sources: dict[str, list[str]] = defaultdict(list)
    for other in layers:
        if other["layer_name"] == layer_name:
            continue
        for ext in other.get("external_edges", []):
            if ext.get("to_layer") == layer_name:
                lbl = ext.get("label", "")
                if lbl:
                    in_sources[other["layer_name"]].append(lbl)
                else:
                    in_sources[other["layer_name"]]

    sb_y = sidebar_y + 28
    sb_w = sidebar_w - 12
    pill_h = 48

    if out_targets:
        cells.append(Cell(
            id="sb-out-h", value="→ Outgoing",
            style=(
                f"text;html=1;strokeColor=none;fillColor=none;"
                f"align=left;verticalAlign=middle;"
                f"fontColor={PALETTE['muted']};fontSize=10;fontStyle=2;"
            ),
            parent="1", vertex=True,
            x=sidebar_x + 6, y=sb_y, w=sb_w, h=18,
        ))
        sb_y += 22
        for tgt, labels in out_targets.items():
            tgt_meta = next((l for l in layers if l["layer_name"] == tgt), None)
            tgt_label = tgt_meta["display_name"] if tgt_meta else tgt
            tgt_accent = accent_by_layer.get(tgt, PALETTE["muted"])
            edge_label = " / ".join(dict.fromkeys(labels))
            value = (
                f"<b>{esc(tgt_label)} →</b>"
                if not edge_label else
                f"<b>{esc(tgt_label)} →</b>"
                f"<br><font size=\"1\" color=\"{PALETTE['subtitle']}\">{esc(edge_label)}</font>"
            )
            cells.append(Cell(
                id=f"sb-out-{tgt}", value=value,
                style=(
                    f"rounded=1;whiteSpace=wrap;html=1;arcSize=8;shadow=1;"
                    f"fillColor={light_fill(tgt_accent)};strokeColor={tgt_accent};strokeWidth=1.5;"
                    f"fontColor={PALETTE['body']};fontSize=11;"
                    f"align=left;verticalAlign=middle;spacingLeft=10;"
                ),
                parent="1", vertex=True,
                x=sidebar_x + 6, y=sb_y, w=sb_w, h=pill_h,
                link=f"data:page/id,{page_id_by_layer[tgt]}",
                tooltip=f"Jump to {tgt_label}",
            ))
            sb_y += pill_h + 6

    if in_sources:
        sb_y += 8
        cells.append(Cell(
            id="sb-in-h", value="← Incoming",
            style=(
                f"text;html=1;strokeColor=none;fillColor=none;"
                f"align=left;verticalAlign=middle;"
                f"fontColor={PALETTE['muted']};fontSize=10;fontStyle=2;"
            ),
            parent="1", vertex=True,
            x=sidebar_x + 6, y=sb_y, w=sb_w, h=18,
        ))
        sb_y += 22
        for src, labels in in_sources.items():
            src_meta = next((l for l in layers if l["layer_name"] == src), None)
            src_label = src_meta["display_name"] if src_meta else src
            src_accent = accent_by_layer.get(src, PALETTE["muted"])
            edge_label = " / ".join(dict.fromkeys(labels))
            value = (
                f"<b>← {esc(src_label)}</b>"
                if not edge_label else
                f"<b>← {esc(src_label)}</b>"
                f"<br><font size=\"1\" color=\"{PALETTE['subtitle']}\">{esc(edge_label)}</font>"
            )
            cells.append(Cell(
                id=f"sb-in-{src}", value=value,
                style=(
                    f"rounded=1;whiteSpace=wrap;html=1;arcSize=8;shadow=1;"
                    f"fillColor={light_fill(src_accent)};strokeColor={src_accent};strokeWidth=1.5;"
                    f"fontColor={PALETTE['body']};fontSize=11;"
                    f"align=left;verticalAlign=middle;spacingLeft=10;"
                ),
                parent="1", vertex=True,
                x=sidebar_x + 6, y=sb_y, w=sb_w, h=pill_h,
                link=f"data:page/id,{page_id_by_layer[src]}",
                tooltip=f"Jump to {src_label}",
            ))
            sb_y += pill_h + 6

    if not out_targets and not in_sources:
        cells.append(Cell(
            id="sb-empty", value="No external connections",
            style=(
                f"text;html=1;strokeColor=none;fillColor=none;"
                f"align=left;verticalAlign=middle;"
                f"fontColor={PALETTE['muted']};fontSize=11;fontStyle=2;"
            ),
            parent="1", vertex=True,
            x=sidebar_x + 6, y=sb_y, w=sb_w, h=22,
        ))

    page_h = max(body_y + body_h + 60, sb_y + 60)
    page_name = f"Layer: {layer['display_name'][:36]}"
    return cells, page_name, page_id, page_w, page_h


# ── Builder: JOURNEY (single-page user flow, light theme) ────────────────────

def build_journey(spec: dict[str, Any]) -> str:
    """Single-page user-journey, light theme.

    Vertical spine layout: user actions on the left, app actions on the right,
    with numbered badges on a central spine. Each step's rich detail
    (description / what_you_see / tips) is delivered as a hover tooltip so the
    page stays scannable.

    Requires `user_flow` in the spec. `phases` is accepted but flattened —
    chapter colors are no longer used in the single-page layout.
    """
    flow = spec.get("user_flow", [])
    if not flow:
        raise ValueError("build_journey requires 'user_flow' in spec")

    USER_COLOR  = "#89B4FA"
    APP_COLOR   = "#A6E3A1"
    SPINE_COLOR = "#CCCCCC"

    page_w     = 1600
    spine_cx   = 800
    spine_w    = 4
    badge_size = 44
    box_h      = 80
    box_gap    = 38
    stride     = box_h + box_gap
    top_y      = 200
    user_box_x = 60
    user_box_w = 680
    app_box_x  = 860
    app_box_w  = 680

    cells: list[Cell] = []

    # Header
    cells.append(Cell(
        id="hdr-title",
        value=esc(spec.get("title", "Project") + " — User Journey"),
        style=header_style(), parent="1", vertex=True,
        x=60, y=18, w=page_w - 120, h=34,
    ))
    if spec.get("subtitle"):
        cells.append(Cell(
            id="hdr-sub", value=esc(spec["subtitle"]),
            style=subtitle_style(), parent="1", vertex=True,
            x=60, y=54, w=page_w - 480, h=22,
        ))
    cells.append(Cell(
        id="hdr-hint", value="Hover any step for details",
        style=hint_style(), parent="1", vertex=True,
        x=60, y=80, w=page_w - 120, h=22,
    ))

    # Persona actor at top of spine
    cells.append(Cell(
        id="hdr-actor", value="<b>You</b>",
        style=actor_shape_style(USER_COLOR),
        parent="1", vertex=True,
        x=spine_cx - 30, y=110, w=60, h=70,
    ))

    # Legend pills
    app_name = spec.get("title", "the app")
    legend_x = page_w - 420
    cells.append(Cell(
        id="lg-user", value="What you do",
        style=capability_style(USER_COLOR), parent="1", vertex=True,
        x=legend_x, y=110, w=140, h=32,
    ))
    cells.append(Cell(
        id="lg-app", value=f"What {esc(app_name)} does",
        style=capability_style(APP_COLOR), parent="1", vertex=True,
        x=legend_x + 160, y=110, w=200, h=32,
    ))

    # Spine (drawn first so badges sit on top)
    n = len(flow)
    first_cy = top_y + box_h // 2
    last_cy  = top_y + (n - 1) * stride + box_h // 2
    cells.append(Cell(
        id="spine", value="",
        style=f"rounded=0;whiteSpace=wrap;html=1;fillColor={SPINE_COLOR};strokeColor=none;",
        parent="1", vertex=True,
        x=spine_cx - spine_w // 2,
        y=first_cy, w=spine_w,
        h=last_cy - first_cy,
    ))

    # Steps
    for i, step in enumerate(flow):
        sid    = step.get("id") or stable_id("step", step.get("label", str(i)))
        actor  = step.get("actor", "user")
        accent = USER_COLOR if actor == "user" else APP_COLOR
        y      = top_y + i * stride

        bx = user_box_x if actor == "user" else app_box_x
        bw = user_box_w if actor == "user" else app_box_w

        # Build a rich tooltip from optional fields
        tooltip_parts: list[str] = []
        if step.get("description"):
            tooltip_parts.append(step["description"])
        if step.get("what_you_see"):
            tooltip_parts.append(f"What you'll see: {step['what_you_see']}")
        if step.get("tips"):
            tooltip_parts.append("Tips: " + " · ".join(step["tips"]))
        tooltip = "\n\n".join(tooltip_parts) or step.get("detail") or step["label"]

        cells.append(Cell(
            id=sid,
            value=html_label(step["label"], step.get("detail")),
            style=node_style(accent),
            parent="1", vertex=True,
            x=bx, y=y, w=bw, h=box_h,
            tooltip=tooltip,
        ))

        badge_y = y + (box_h - badge_size) // 2
        cells.append(Cell(
            id=f"badge-{sid}", value=f"<b>{i + 1}</b>",
            style=(
                f"ellipse;whiteSpace=wrap;html=1;shadow=1;"
                f"fillColor={accent};strokeColor=#FFFFFF;strokeWidth=2;"
                f"fontColor=#FFFFFF;fontSize=14;fontStyle=1;"
            ),
            parent="1", vertex=True,
            x=spine_cx - badge_size // 2,
            y=badge_y, w=badge_size, h=badge_size,
        ))

    page_h = top_y + n * stride + 60
    return render_mxfile(cells, name="Journey", page_w=page_w, page_h=page_h)


# ── main() ──────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", help="Path to spec JSON (default: stdin)")
    ap.add_argument("--out-portfolio", required=True)
    ap.add_argument("--out-detailed", required=True)
    ap.add_argument(
        "--out-journey",
        help=(
            "Optional third diagram: single-page user-flow journey for "
            "non-technical audiences. Requires 'user_flow' in spec."
        ),
    )
    args = ap.parse_args()

    if args.spec:
        spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    else:
        spec = json.loads(sys.stdin.read())

    for layer in spec.get("layers", []):
        ln = layer.get("layer_name", "").lower()
        layer["layer_name"] = ln
        if ln not in LAYER_SHORT:
            LAYER_SHORT[ln] = ln[:2]

    portfolio_xml = build_portfolio(spec)
    detailed_xml = build_detailed(spec)

    Path(args.out_portfolio).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_portfolio).write_text(portfolio_xml, encoding="utf-8")
    Path(args.out_detailed).write_text(detailed_xml, encoding="utf-8")

    print(f"portfolio: {args.out_portfolio}")
    print(f"detailed:  {args.out_detailed}")

    if args.out_journey:
        journey_xml = build_journey(spec)
        Path(args.out_journey).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out_journey).write_text(journey_xml, encoding="utf-8")
        print(f"journey:   {args.out_journey}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
