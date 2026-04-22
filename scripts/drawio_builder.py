#!/usr/bin/env python3
"""
drawio_builder.py — Turn a graph spec JSON into two `.drawio` XML files.

Input (via --spec <file> or stdin):
  {
    "title": "MyProject",
    "subtitle": "one-line pitch",
    "layers": [ { ...layer schema... }, ... ]
  }

Outputs (via --out-portfolio, --out-detailed):
  Two valid draw.io XML files, dark-themed, swimlane-structured.

Why a script instead of hand-writing XML in the skill:
- Keeps the skill body short (progressive disclosure).
- Guarantees valid XML, unique IDs, consistent geometry math.
- Preserves node IDs across regens when --previous-* is passed, so PR diffs stay minimal.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PALETTE = {
    "canvas": "#1E1E2E",
    "lane_bg": "#2D2D3A",
    "text": "#CDD6F4",
    "muted": "#9399B2",
    "emphasis": "#F5E0DC",
}

LAYER_SHORT = {
    "frontend": "fe", "mobile": "mo", "backend": "be", "api": "be",
    "data": "da", "jobs": "jb", "workers": "jb", "integrations": "ig",
    "infra": "in", "docs": "dc", "assets": "dc",
}


def esc(s: str) -> str:
    """XML-attribute escape. Use on every user-provided string."""
    return html.escape(s or "", quote=True)


def html_label(main: str, sub: str | None = None) -> str:
    """Build an HTML node label: bold main + small muted sub."""
    if sub:
        return (
            f"<b>{esc(main)}</b>"
            f"<br><font size=\"1\" color=\"{PALETTE['muted']}\">{esc(sub)}</font>"
        )
    return f"<b>{esc(main)}</b>"


def stable_id(prefix: str, seed: str) -> str:
    """Short deterministic id from a seed string — used for edges where the spec
    didn't pre-assign one. Deterministic so regens don't churn IDs."""
    h = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:8]
    return f"{prefix}-{h}"


def light_fill(accent: str) -> str:
    """Blend accent color 20% toward white — for group/node backgrounds."""
    try:
        r = int(accent[1:3], 16) * 0.22 + 255 * 0.78
        g = int(accent[3:5], 16) * 0.22 + 255 * 0.78
        b = int(accent[5:7], 16) * 0.22 + 255 * 0.78
        return f"#{int(r):02X}{int(g):02X}{int(b):02X}"
    except (ValueError, IndexError):
        return "#F5F5F5"


def darker(accent: str, factor: float = 0.72) -> str:
    """Darken an accent color by a factor — used for gradient endpoints."""
    try:
        r = max(0, int(int(accent[1:3], 16) * factor))
        g = max(0, int(int(accent[3:5], 16) * factor))
        b = max(0, int(int(accent[5:7], 16) * factor))
        return f"#{r:02X}{g:02X}{b:02X}"
    except (ValueError, IndexError):
        return "#333333"


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


def lane_style(accent: str) -> str:
    return (
        f"swimlane;horizontal=0;startSize=36;"
        f"fillColor={PALETTE['lane_bg']};strokeColor={accent};strokeWidth=2;"
        f"fontColor={PALETTE['text']};fontStyle=1;fontSize=14;rounded=1;arcSize=6;"
        f"swimlaneFillColor={PALETTE['canvas']};"
    )


def node_style(accent: str) -> str:
    return (
        f"rounded=1;whiteSpace=wrap;html=1;arcSize=12;shadow=0;"
        f"fillColor={PALETTE['canvas']};strokeColor={accent};strokeWidth=1.5;"
        f"fontColor={PALETTE['text']};fontSize=12;"
    )


def capability_style(accent: str) -> str:
    return (
        f"rounded=1;whiteSpace=wrap;html=1;arcSize=40;shadow=0;"
        f"fillColor={accent};strokeColor=none;"
        f"fontColor={PALETTE['canvas']};fontSize=11;fontStyle=1;"
    )


def badge_style(accent: str) -> str:
    return (
        f"rounded=1;whiteSpace=wrap;html=1;arcSize=40;shadow=0;"
        f"fillColor={accent};strokeColor=none;"
        f"fontColor={PALETTE['canvas']};fontSize=10;fontStyle=1;"
        f"spacingLeft=6;spacingRight=6;"
    )


def edge_style(emphasis: bool = False, color: str | None = None) -> str:
    stroke = color or (PALETTE["emphasis"] if emphasis else PALETTE["muted"])
    return (
        f"endArrow=classic;html=1;rounded=0;curved=1;"
        f"strokeColor={stroke};strokeWidth=1.5;"
        f"fontColor={PALETTE['text']};fontSize=10;"
        f"labelBackgroundColor={PALETTE['canvas']};"
    )


def portfolio_edge_style(src_above: bool, color: str) -> str:
    """Lane-to-lane edge with pinned exit/entry points and source-layer color."""
    if src_above:
        pins = "exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;"
    else:
        pins = "exitX=0.5;exitY=0;exitDx=0;exitDy=0;entryX=0.5;entryY=1;entryDx=0;entryDy=0;"
    return (
        f"endArrow=classic;html=1;rounded=0;curved=1;{pins}"
        f"strokeColor={color};strokeWidth=2;"
        f"fontColor={PALETTE['text']};fontSize=10;"
        f"labelBackgroundColor={PALETTE['canvas']};"
    )


def header_style() -> str:
    return (
        f"text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;"
        f"fontColor={PALETTE['text']};fontSize=22;fontStyle=1;"
    )


def subtitle_style() -> str:
    return (
        f"text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;"
        f"fontColor={PALETTE['muted']};fontSize=12;"
    )


# ── Light-theme styles (ai-dev-workflow visual language) ─────────────────────

def group_container_style(accent: str) -> str:
    """Dashed group container — matches ai-dev-workflow.drawio group blocks."""
    return (
        f"rounded=1;whiteSpace=wrap;html=1;shadow=1;"
        f"fillColor={light_fill(accent)};strokeColor={accent};strokeWidth=2;"
        f"dashed=1;dashPattern=8 4;"
        f"verticalAlign=top;align=left;spacingLeft=12;spacingTop=8;"
        f"fontColor={accent};fontSize=13;fontStyle=1;"
    )


def flownode_style(accent: str) -> str:
    """Light-fill node for the detailed flowchart diagram."""
    return (
        f"rounded=1;whiteSpace=wrap;html=1;arcSize=8;shadow=1;"
        f"fillColor={light_fill(accent)};strokeColor={accent};strokeWidth=1.5;"
        f"fontColor=#333333;fontSize=11;"
    )


def flowbadge_style(accent: str) -> str:
    """Tech badge pill in light theme."""
    return (
        f"rounded=1;whiteSpace=wrap;html=1;arcSize=40;"
        f"fillColor={accent};strokeColor=none;"
        f"fontColor=#FFFFFF;fontSize=9;fontStyle=1;"
        f"spacingLeft=5;spacingRight=5;"
    )


def ortho_edge_style(color: str, src_above: bool | None = None) -> str:
    """Orthogonal routed edge — matches ai-dev-workflow edge style."""
    pins = ""
    if src_above is True:
        pins = "exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;"
    elif src_above is False:
        pins = "exitX=0.5;exitY=0;exitDx=0;exitDy=0;entryX=0.5;entryY=1;entryDx=0;entryDy=0;"
    return (
        f"edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;{pins}"
        f"strokeColor={color};strokeWidth=1.5;"
        f"fontColor=#555555;fontSize=10;"
        f"labelBackgroundColor=#FFFFFF;"
    )


def html_label_dark(main: str, sub: str | None = None) -> str:
    """HTML label with dark text — used in light-theme detailed diagram."""
    if sub:
        return (
            f"<b>{esc(main)}</b>"
            f"<br><font size=\"1\" color=\"#666666\">{esc(sub)}</font>"
        )
    return f"<b>{esc(main)}</b>"


def build_flow_overview(
    spec: dict[str, Any],
    phases: list[dict],
    step_by_id: dict[str, dict],
    overview_page_id: str,
) -> tuple[list[Cell], str, str, int, int]:
    """Overview page: 3 horizontal phase cards, each clickable."""
    page_w    = 1400
    header_h  = 88
    cards_y   = header_h + 24
    card_w    = 380
    card_h    = 286
    card_gap  = 30
    n = len(phases)
    total_w = n * card_w + (n - 1) * card_gap
    left_x  = (page_w - total_w) // 2

    cells: list[Cell] = []

    cells.append(Cell(
        id="ov-title", value=esc(spec.get("title", "Project")),
        style=header_style(), parent="1", vertex=True,
        x=40, y=18, w=page_w - 80, h=36,
    ))
    if spec.get("subtitle"):
        cells.append(Cell(
            id="ov-sub", value=esc(spec["subtitle"]),
            style=subtitle_style(), parent="1", vertex=True,
            x=40, y=56, w=page_w - 80, h=22,
        ))
    cells.append(Cell(
        id="ov-hint", value="Click a phase to explore its steps",
        style=(
            f"text;html=1;strokeColor=none;fillColor=none;align=right;"
            f"verticalAlign=middle;fontColor={PALETTE['muted']};fontSize=11;fontStyle=2;"
        ),
        parent="1", vertex=True,
        x=page_w - 320, y=56, w=280, h=22,
    ))

    for i, phase in enumerate(phases):
        cx     = left_x + i * (card_w + card_gap)
        accent = phase["accent"]
        pid    = phase["id"]

        # Card background (clickable)
        cells.append(Cell(
            id=f"ph-card-{pid}", value="",
            style=(
                f"rounded=1;whiteSpace=wrap;html=1;arcSize=8;shadow=1;"
                f"fillColor={PALETTE['lane_bg']};gradientColor={PALETTE['canvas']};gradientDirection=south;"
                f"strokeColor={accent};strokeWidth=3;"
            ),
            parent="1", vertex=True,
            x=cx, y=cards_y, w=card_w, h=card_h,
            link=f"data:page/id,{pid}",
            tooltip=f"Explore the {phase['label']} phase",
        ))
        # Thin accent top strip — color-codes the card from top edge
        cells.append(Cell(
            id=f"ph-topbar-{pid}", value="",
            style=f"rounded=1;whiteSpace=wrap;html=1;arcSize=50;fillColor={accent};strokeColor=none;",
            parent="1", vertex=True,
            x=cx + 2, y=cards_y + 2, w=card_w - 4, h=6,
        ))

        # Phase number badge
        cells.append(Cell(
            id=f"ph-badge-{pid}", value=f"<b>{i + 1}</b>",
            style=(
                f"ellipse;whiteSpace=wrap;html=1;shadow=1;"
                f"fillColor={accent};strokeColor={PALETTE['canvas']};strokeWidth=2;"
                f"fontColor={PALETTE['canvas']};fontSize=18;fontStyle=1;"
            ),
            parent="1", vertex=True,
            x=cx + 16, y=cards_y + 16, w=52, h=52,
        ))

        # Phase label
        cells.append(Cell(
            id=f"ph-label-{pid}", value=f"<b>{esc(phase['label'])}</b>",
            style=(
                f"text;html=1;strokeColor=none;fillColor=none;"
                f"align=left;verticalAlign=middle;"
                f"fontColor={accent};fontSize=20;fontStyle=1;"
            ),
            parent="1", vertex=True,
            x=cx + 80, y=cards_y + 20, w=card_w - 96, h=44,
        ))

        # Tagline + step count
        step_ids = phase.get("step_ids", [])
        tagline_text = phase.get("tagline", "")
        count_text = f"{len(step_ids)} steps" if step_ids else ""
        tagline_full = f"{tagline_text}  ·  {count_text}" if tagline_text and count_text else tagline_text or count_text
        if tagline_full:
            cells.append(Cell(
                id=f"ph-tagline-{pid}", value=esc(tagline_full),
                style=(
                    f"text;html=1;strokeColor=none;fillColor=none;"
                    f"align=left;verticalAlign=top;whiteSpace=wrap;"
                    f"fontColor={PALETTE['muted']};fontSize=11;fontStyle=2;"
                ),
                parent="1", vertex=True,
                x=cx + 20, y=cards_y + 76, w=card_w - 40, h=22,
            ))

        # Separator
        cells.append(Cell(
            id=f"ph-sep-{pid}", value="",
            style=f"rounded=0;whiteSpace=wrap;html=1;fillColor={accent};strokeColor=none;opacity=40;",
            parent="1", vertex=True,
            x=cx + 20, y=cards_y + 104, w=card_w - 40, h=2,
        ))

        # Step reference labels (tighter spacing)
        for j, sid in enumerate(step_ids[:3]):
            step  = step_by_id.get(sid, {})
            slabel = step.get("label", sid)
            cells.append(Cell(
                id=f"ph-sref-{pid}-{j}", value=f"<b>{j + 1}.</b>  {esc(slabel)}",
                style=(
                    f"text;html=1;strokeColor=none;fillColor=none;"
                    f"align=left;verticalAlign=middle;"
                    f"fontColor={PALETTE['text']};fontSize=12;"
                ),
                parent="1", vertex=True,
                x=cx + 28, y=cards_y + 114 + j * 42, w=card_w - 56, h=36,
            ))

        # "Explore →" CTA button
        cells.append(Cell(
            id=f"ph-cta-{pid}", value=f"Explore {esc(phase['label'])} →",
            style=(
                f"rounded=1;whiteSpace=wrap;html=1;arcSize=40;shadow=1;"
                f"fillColor={accent};gradientColor={darker(accent)};gradientDirection=south;"
                f"strokeColor=none;"
                f"fontColor={PALETTE['canvas']};fontSize=12;fontStyle=1;"
            ),
            parent="1", vertex=True,
            x=cx + 20, y=cards_y + card_h - 52, w=card_w - 40, h=36,
            link=f"data:page/id,{pid}",
        ))

    # Arrows between phase cards
    for i in range(n - 1):
        cells.append(Cell(
            id=f"ph-arrow-{i}", value="",
            style=(
                f"endArrow=classic;html=1;rounded=0;"
                f"exitX=1;exitY=0.5;exitDx=0;exitDy=0;"
                f"entryX=0;entryY=0.5;entryDx=0;entryDy=0;"
                f"strokeColor={PALETTE['muted']};strokeWidth=2;"
            ),
            parent="1", edge=True,
            source=f"ph-card-{phases[i]['id']}",
            target=f"ph-card-{phases[i + 1]['id']}",
        ))

    page_h = cards_y + card_h + 60
    return cells, "How It Works", overview_page_id, page_w, page_h


def build_phase_page(
    phase: dict,
    steps: list[dict],
    overview_page_id: str,
) -> tuple[list[Cell], str, str, int, int]:
    """Phase detail page: cards with integrated colored header strips."""
    USER_COLOR  = "#89B4FA"
    APP_COLOR   = "#A6E3A1"
    accent      = phase["accent"]
    phase_id    = phase["id"]

    page_w      = 1400
    header_h    = 114
    step_y      = header_h + 20
    card_hdr_h  = 68    # colored strip at top of each card
    card_body_h = 160   # content area below strip
    step_w      = 360
    step_h      = card_hdr_h + card_body_h
    arr_gap     = 24
    n           = len(steps)
    total_w     = n * step_w + (n - 1) * arr_gap
    left_x      = (page_w - total_w) // 2

    cells: list[Cell] = []

    # Nav row
    cells.append(Cell(
        id="pp-back", value="← Overview",
        style=(
            f"rounded=1;whiteSpace=wrap;html=1;arcSize=40;"
            f"fillColor={PALETTE['lane_bg']};strokeColor={PALETTE['muted']};"
            f"fontColor={PALETTE['text']};fontSize=11;"
        ),
        parent="1", vertex=True,
        x=40, y=20, w=120, h=30,
        link=f"data:page/id,{overview_page_id}",
        tooltip="Return to the main overview",
    ))
    cells.append(Cell(
        id="pp-label", value=f"<b>{esc(phase['label'])}</b>",
        style=(
            f"text;html=1;strokeColor=none;fillColor=none;"
            f"align=left;verticalAlign=middle;"
            f"fontColor={accent};fontSize=24;fontStyle=1;"
        ),
        parent="1", vertex=True,
        x=40, y=58, w=700, h=36,
    ))
    if phase.get("tagline"):
        cells.append(Cell(
            id="pp-tagline", value=esc(phase["tagline"]),
            style=(
                f"text;html=1;strokeColor=none;fillColor=none;"
                f"align=left;verticalAlign=middle;"
                f"fontColor={PALETTE['muted']};fontSize=13;fontStyle=2;"
            ),
            parent="1", vertex=True,
            x=40, y=94, w=700, h=22,
        ))
    cells.append(Cell(
        id="pp-hint", value="Click a step to learn more",
        style=(
            f"text;html=1;strokeColor=none;fillColor=none;align=right;"
            f"verticalAlign=middle;fontColor={PALETTE['muted']};fontSize=11;fontStyle=2;"
        ),
        parent="1", vertex=True,
        x=page_w - 260, y=72, w=220, h=22,
    ))

    for i, step in enumerate(steps):
        sx          = left_x + i * (step_w + arr_gap)
        sid         = step["id"]
        step_actor  = step.get("actor", "user")
        step_accent = USER_COLOR if step_actor == "user" else APP_COLOR
        actor_text  = "YOU" if step_actor == "user" else "APP"

        # ── Card background (clickable, full height) ──────────────
        cells.append(Cell(
            id=f"pp-card-{sid}", value="",
            style=(
                f"rounded=1;whiteSpace=wrap;html=1;arcSize=6;shadow=1;"
                f"fillColor={PALETTE['canvas']};gradientColor={PALETTE['lane_bg']};gradientDirection=south;"
                f"strokeColor={step_accent};strokeWidth=2;"
            ),
            parent="1", vertex=True,
            x=sx, y=step_y, w=step_w, h=step_h,
            link=f"data:page/id,{sid}",
            tooltip=step.get("description") or step.get("detail") or step["label"],
        ))

        # ── Colored header strip inside card ──────────────────────
        cells.append(Cell(
            id=f"pp-hdr-{sid}", value="",
            style=(
                f"rounded=1;whiteSpace=wrap;html=1;arcSize=10;"
                f"fillColor={step_accent};gradientColor={darker(step_accent)};gradientDirection=east;"
                f"strokeColor=none;"
            ),
            parent="1", vertex=True,
            x=sx + 2, y=step_y + 2, w=step_w - 4, h=card_hdr_h - 2,
        ))

        # ── Step number circle (dark on accent) ───────────────────
        cells.append(Cell(
            id=f"pp-num-{sid}", value=f"<b>{i + 1}</b>",
            style=(
                f"ellipse;whiteSpace=wrap;html=1;"
                f"fillColor={PALETTE['canvas']};strokeColor=none;"
                f"fontColor={step_accent};fontSize=17;fontStyle=1;"
            ),
            parent="1", vertex=True,
            x=sx + 12, y=step_y + 14, w=40, h=40,
        ))

        # ── Step label in header strip ────────────────────────────
        cells.append(Cell(
            id=f"pp-lbl-{sid}", value=f"<b>{esc(step['label'])}</b>",
            style=(
                f"text;html=1;strokeColor=none;fillColor=none;"
                f"align=left;verticalAlign=middle;whiteSpace=wrap;"
                f"fontColor={PALETTE['canvas']};fontSize=12;fontStyle=1;"
            ),
            parent="1", vertex=True,
            x=sx + 62, y=step_y + 6, w=step_w - 74, h=card_hdr_h - 12,
        ))

        # ── Actor pill in card body ───────────────────────────────
        cells.append(Cell(
            id=f"pp-actor-{sid}", value=actor_text,
            style=(
                f"rounded=1;whiteSpace=wrap;html=1;arcSize=40;"
                f"fillColor={step_accent};strokeColor=none;"
                f"fontColor={PALETTE['canvas']};fontSize=9;fontStyle=1;"
            ),
            parent="1", vertex=True,
            x=sx + step_w - 56, y=step_y + card_hdr_h + 10, w=44, h=20,
        ))

        # ── Subtitle / detail text ────────────────────────────────
        detail = step.get("detail", "")
        if detail:
            cells.append(Cell(
                id=f"pp-detail-{sid}", value=esc(detail),
                style=(
                    f"text;html=1;strokeColor=none;fillColor=none;"
                    f"align=left;verticalAlign=top;whiteSpace=wrap;"
                    f"fontColor={PALETTE['muted']};fontSize=12;fontStyle=2;"
                ),
                parent="1", vertex=True,
                x=sx + 14, y=step_y + card_hdr_h + 10, w=step_w - 72, h=68,
            ))

        # ── "Tap to learn more →" ─────────────────────────────────
        cells.append(Cell(
            id=f"pp-more-{sid}", value="Tap to learn more →",
            style=(
                f"text;html=1;strokeColor=none;fillColor=none;"
                f"align=left;verticalAlign=middle;"
                f"fontColor={step_accent};fontSize=11;fontStyle=2;"
            ),
            parent="1", vertex=True,
            x=sx + 14, y=step_y + step_h - 30, w=step_w - 28, h=22,
        ))

    # Arrows between cards (source/target = card bg cells)
    for i in range(n - 1):
        cells.append(Cell(
            id=f"pp-arrow-{i}", value="",
            style=(
                f"endArrow=classic;html=1;rounded=0;"
                f"exitX=1;exitY=0.5;exitDx=0;exitDy=0;"
                f"entryX=0;entryY=0.5;entryDx=0;entryDy=0;"
                f"strokeColor={accent};strokeWidth=2;"
            ),
            parent="1", edge=True,
            source=f"pp-card-{steps[i]['id']}",
            target=f"pp-card-{steps[i + 1]['id']}",
        ))

    page_h = step_y + step_h + 60
    return cells, phase["label"], phase_id, page_w, page_h


def build_portfolio_phased(
    spec: dict[str, Any],
    flow: list[dict],
    phases: list[dict],
) -> str:
    """Portfolio with 3-level hierarchy: Overview → Phase → Step detail."""
    overview_page_id = "portfolio-overview"
    step_by_id = {step["id"]: step for step in flow}
    app_name = spec.get("title", "the app")

    pages: list[tuple[list[Cell], str, str, int, int]] = [
        build_flow_overview(spec, phases, step_by_id, overview_page_id)
    ]

    for phase in phases:
        steps = [step_by_id[sid] for sid in phase.get("step_ids", []) if sid in step_by_id]
        pages.append(build_phase_page(phase, steps, overview_page_id))
        for i, step in enumerate(steps):
            next_step = steps[i + 1] if i + 1 < len(steps) else None
            pages.append(
                build_step_page(step, i + 1, len(steps), next_step, phase["id"],
                                back_label=f"← {phase['label']}", app_name=app_name)
            )

    return render_mxfile_paged(pages)


def build_portfolio_flow(spec: dict[str, Any]) -> str:
    """Portfolio as a user-journey with a central spine + numbered badges.

    No box-to-box arrows. The vertical spine line communicates direction.
    User steps sit on the LEFT, app steps on the RIGHT.
    Each box is clickable and opens a detail page.
    """
    flow   = spec.get("user_flow", [])
    phases = spec.get("phases", [])
    if phases:
        return build_portfolio_phased(spec, flow, phases)
    main_page_id = "portfolio-main"

    USER_COLOR  = "#89B4FA"
    APP_COLOR   = "#A6E3A1"
    SPINE_COLOR = "#3D3D55"

    page_w      = 1220
    spine_cx    = 610       # horizontal center of spine
    spine_w     = 6
    badge_size  = 44
    box_h       = 80
    box_gap     = 52        # breathing room between steps
    stride      = box_h + box_gap
    top_y       = 164
    user_box_x  = 48
    user_box_w  = 520       # right edge at 568, badge left at 588 — 20px gap
    app_box_x   = 652       # left edge at 652, badge right at 632 — 20px gap
    app_box_w   = 520

    cells: list[Cell] = []

    # ── Header ───────────────────────────────────────────────
    cells.append(Cell(
        id="hdr-title", value=esc(spec.get("title", "Project")),
        style=header_style(), parent="1", vertex=True,
        x=48, y=16, w=page_w - 96, h=34,
    ))
    if spec.get("subtitle"):
        cells.append(Cell(
            id="hdr-sub", value=esc(spec["subtitle"]),
            style=subtitle_style(), parent="1", vertex=True,
            x=48, y=52, w=page_w - 360, h=22,
        ))

    cells.append(Cell(
        id="hdr-hint", value="Click any step to learn more",
        style=(
            f"text;html=1;strokeColor=none;fillColor=none;align=right;"
            f"verticalAlign=middle;fontColor={PALETTE['muted']};fontSize=11;fontStyle=2;"
        ),
        parent="1", vertex=True,
        x=page_w - 280, y=52, w=240, h=22,
    ))

    # Legend pills
    app_name = spec.get("title", "the app")
    for i, (lbl, color) in enumerate([
        ("What you do", USER_COLOR),
        (f"What {app_name} does", APP_COLOR),
    ]):
        pill_w = max(120, 10 + 9 * len(lbl))
        cells.append(Cell(
            id=f"legend-{i}", value=esc(lbl),
            style=(
                f"rounded=1;whiteSpace=wrap;html=1;arcSize=40;"
                f"fillColor={color};strokeColor=none;"
                f"fontColor={PALETTE['canvas']};fontSize=12;fontStyle=1;"
            ),
            parent="1", vertex=True,
            x=48 + i * (pill_w + 10), y=84, w=pill_w, h=26,
        ))

    # ── Spine (drawn first so badges render on top) ──────────
    n = len(flow)
    first_badge_cy = top_y + box_h // 2
    last_badge_cy  = top_y + (n - 1) * stride + box_h // 2
    cells.append(Cell(
        id="spine", value="",
        style=f"rounded=0;whiteSpace=wrap;html=1;fillColor={SPINE_COLOR};strokeColor=none;",
        parent="1", vertex=True,
        x=spine_cx - spine_w // 2,
        y=first_badge_cy,
        w=spine_w,
        h=last_badge_cy - first_badge_cy,
    ))

    # ── Step boxes + badges ──────────────────────────────────
    for i, step in enumerate(flow):
        sid    = step["id"]
        actor  = step.get("actor", "user")
        accent = USER_COLOR if actor == "user" else APP_COLOR
        y      = top_y + i * stride

        # Step box
        bx = user_box_x if actor == "user" else app_box_x
        bw = user_box_w if actor == "user" else app_box_w
        label = html_label(step["label"], step.get("detail"))
        cells.append(Cell(
            id=sid, value=label,
            style=(
                f"rounded=1;whiteSpace=wrap;html=1;arcSize=12;"
                f"fillColor={PALETTE['canvas']};strokeColor={accent};strokeWidth=2.5;"
                f"fontColor={PALETTE['text']};fontSize=13;"
            ),
            parent="1", vertex=True,
            x=bx, y=y, w=bw, h=box_h,
            link=f"data:page/id,{sid}",
            tooltip=step.get("description") or step.get("detail") or step["label"],
        ))

        # Numbered badge sitting on the spine
        badge_y = y + (box_h - badge_size) // 2
        cells.append(Cell(
            id=f"badge-{sid}",
            value=f"<b>{i + 1}</b>",
            style=(
                f"ellipse;whiteSpace=wrap;html=1;"
                f"fillColor={accent};strokeColor={PALETTE['canvas']};strokeWidth=2;"
                f"fontColor={PALETTE['canvas']};fontSize=14;fontStyle=1;"
            ),
            parent="1", vertex=True,
            x=spine_cx - badge_size // 2,
            y=badge_y,
            w=badge_size, h=badge_size,
        ))

    page_h = top_y + n * stride + 60

    # ── Assemble all pages ───────────────────────────────────
    pages: list[tuple[list[Cell], str, str, int, int]] = [
        (cells, "How It Works", main_page_id, page_w, page_h),
    ]
    for i, step in enumerate(flow):
        next_step = flow[i + 1] if i + 1 < len(flow) else None
        pages.append(build_step_page(step, i + 1, len(flow), next_step, main_page_id, app_name=app_name))

    return render_mxfile_paged(pages)


def build_journey(spec: dict[str, Any]) -> str:
    """Journey diagram — multi-page interactive user flow.

    Designed for non-technical audiences (recruiters, family, end users).
    Pure user journey, zero backend jargon. Requires `phases` and/or
    `user_flow` in spec.
    """
    if not spec.get("user_flow") and not spec.get("phases"):
        raise ValueError(
            "build_journey requires 'user_flow' or 'phases' in spec"
        )
    return build_portfolio_flow(spec)


def build_portfolio(spec: dict[str, Any]) -> str:
    """Portfolio diagram — capability pills + tech badges, spacious."""
    cells: list[Cell] = []
    layers = spec.get("layers", [])

    page_w, left_margin, top_margin = 1600, 40, 96
    lane_w = page_w - 2 * left_margin
    lane_h = 168  # extra bottom padding vs 150
    lane_gap = 28

    # Header
    cells.append(Cell(
        id="hdr-title", value=esc(spec.get("title", "Project")),
        style=header_style(), parent="1", vertex=True,
        x=left_margin, y=20, w=lane_w, h=32,
    ))
    if spec.get("subtitle"):
        cells.append(Cell(
            id="hdr-sub", value=esc(spec["subtitle"]),
            style=subtitle_style(), parent="1", vertex=True,
            x=left_margin, y=54, w=lane_w, h=24,
        ))

    lane_ids_by_name: dict[str, str] = {}
    idx_by_layer: dict[str, int] = {}
    accent_by_layer: dict[str, str] = {}

    for idx, layer in enumerate(layers):
        lane_y = top_margin + idx * (lane_h + lane_gap)
        lane_id = f"lane-p-{layer['layer_name']}"
        accent = layer["accent"]

        lane_ids_by_name[layer["layer_name"]] = lane_id
        idx_by_layer[layer["layer_name"]] = idx
        accent_by_layer[layer["layer_name"]] = accent

        cells.append(Cell(
            id=lane_id, value=esc(layer["display_name"].upper()),
            style=lane_style(accent), parent="1", vertex=True,
            x=left_margin, y=lane_y, w=lane_w, h=lane_h,
        ))

        # Tech badges — top strip of the lane body
        badge_x = 48
        for btext in layer.get("tech_badges", [])[:5]:
            bw = max(60, 10 + 8 * len(btext))
            cells.append(Cell(
                id=stable_id(f"{lane_id}-badge", btext),
                value=esc(btext),
                style=badge_style(accent), parent=lane_id, vertex=True,
                x=badge_x, y=8, w=bw, h=22,
            ))
            badge_x += bw + 8

        # Capability pills — balanced row layout
        caps = layer.get("capabilities", [])[:6]
        cap_w = 280
        cap_h = 46
        cap_gap_x = 24
        cap_gap_y = 14
        # ≤4 caps: single row; 5-6: two balanced rows (ceil(n/2) per row)
        if len(caps) <= 4:
            cols = max(1, len(caps))
        else:
            cols = math.ceil(len(caps) / 2)
        start_x = 48
        start_y = 44
        for i, cap in enumerate(caps):
            row, col = divmod(i, cols)
            cap_id = stable_id(f"{lane_id}-cap", cap)
            cells.append(Cell(
                id=cap_id,
                value=esc(cap),
                style=capability_style(accent), parent=lane_id, vertex=True,
                x=start_x + col * (cap_w + cap_gap_x),
                y=start_y + row * (cap_h + cap_gap_y),
                w=cap_w, h=cap_h,
            ))

    # Cross-layer edges — lane-to-lane, de-duplicated, colored by source accent
    # Group all external edges by (src_layer, tgt_layer) and merge labels.
    edge_groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for layer in layers:
        for ext in layer.get("external_edges", []):
            tgt = ext.get("to_layer", "")
            if tgt not in lane_ids_by_name:
                continue
            key = (layer["layer_name"], tgt)
            lbl = ext.get("label", "")
            if lbl:
                edge_groups[key].append(lbl)
            else:
                edge_groups[key]  # ensure key exists even with no label

    for (src_layer, tgt_layer), labels in edge_groups.items():
        src_lane = lane_ids_by_name[src_layer]
        tgt_lane = lane_ids_by_name[tgt_layer]
        merged = " / ".join(dict.fromkeys(labels))  # de-dup preserving order
        src_above = idx_by_layer[src_layer] < idx_by_layer[tgt_layer]
        color = accent_by_layer[src_layer]
        eid = stable_id("ep", f"{src_layer}->{tgt_layer}")
        cells.append(Cell(
            id=eid, value=esc(merged),
            style=portfolio_edge_style(src_above, color),
            parent="1", edge=True,
            source=src_lane, target=tgt_lane,
        ))

    page_h = top_margin + len(layers) * (lane_h + lane_gap) + 40
    return render_mxfile(cells, name="Portfolio", page_w=page_w, page_h=page_h)


def build_detailed(spec: dict[str, Any]) -> str:
    """Detailed architecture — light canvas, dashed group containers, orthogonal edges.

    Visual language matches ai-dev-workflow.drawio: white background, pastel group fills,
    dashed outlines, orthogonal edge routing, dark text.
    """
    cells: list[Cell] = []
    layers = spec.get("layers", [])

    page_w      = 2000
    left_margin = 40
    top_margin  = 96
    grp_w       = page_w - 2 * left_margin
    grp_h       = 290
    grp_gap     = 24

    accent_by_layer: dict[str, str] = {layer["layer_name"]: layer["accent"] for layer in layers}
    idx_by_layer:   dict[str, int]  = {layer["layer_name"]: i for i, layer in enumerate(layers)}

    # ── Header ────────────────────────────────────────────────
    cells.append(Cell(
        id="hdr-title",
        value=esc(spec.get("title", "Project") + " — Architecture"),
        style=(
            "text;html=1;strokeColor=none;fillColor=none;"
            "align=left;verticalAlign=middle;"
            "fontColor=#222222;fontSize=22;fontStyle=1;"
        ),
        parent="1", vertex=True,
        x=left_margin, y=20, w=grp_w, h=32,
    ))
    if spec.get("subtitle"):
        cells.append(Cell(
            id="hdr-sub", value=esc(spec["subtitle"]),
            style=(
                "text;html=1;strokeColor=none;fillColor=none;"
                "align=left;verticalAlign=middle;"
                "fontColor=#666666;fontSize=12;"
            ),
            parent="1", vertex=True,
            x=left_margin, y=54, w=grp_w, h=22,
        ))

    all_node_ids_by_layer: dict[str, list[tuple[str, str]]] = {}

    for idx, layer in enumerate(layers):
        grp_y  = top_margin + idx * (grp_h + grp_gap)
        grp_id = f"grp-{layer['layer_name']}"
        accent = layer["accent"]

        # ── Dashed group container ────────────────────────────
        cells.append(Cell(
            id=grp_id,
            value=esc(layer["display_name"].upper()),
            style=group_container_style(accent),
            parent="1", vertex=True,
            x=left_margin, y=grp_y, w=grp_w, h=grp_h,
        ))

        # ── Tech badges ───────────────────────────────────────
        badge_x = 14
        for btext in layer.get("tech_badges", [])[:7]:
            bw = max(52, 8 + 7 * len(btext))
            cells.append(Cell(
                id=stable_id(f"{grp_id}-badge", btext),
                value=esc(btext),
                style=flowbadge_style(accent),
                parent=grp_id, vertex=True,
                x=badge_x, y=38, w=bw, h=20,
            ))
            badge_x += bw + 6

        # ── Key nodes — 5-column grid ─────────────────────────
        nodes   = layer.get("key_nodes", [])[:18]
        node_w  = 200
        node_h  = 62
        gap_x   = 16
        gap_y   = 14
        cols    = 5
        start_x = 14
        start_y = 68

        layer_nodes: list[tuple[str, str]] = []
        for i, node in enumerate(nodes):
            row, col = divmod(i, cols)
            label = html_label_dark(
                node.get("label", node.get("id", "?")),
                node.get("file_path") or node.get("detail"),
            )
            nid = node.get("id") or stable_id(f"{grp_id}-n", node.get("label", str(i)))
            cells.append(Cell(
                id=nid, value=label,
                style=flownode_style(accent),
                parent=grp_id, vertex=True,
                x=start_x + col * (node_w + gap_x),
                y=start_y + row * (node_h + gap_y),
                w=node_w, h=node_h,
            ))
            layer_nodes.append((nid, node.get("label", "")))
        all_node_ids_by_layer[layer["layer_name"]] = layer_nodes

    # ── Internal edges ────────────────────────────────────────
    for layer in layers:
        accent = layer["accent"]
        for e in layer.get("internal_edges", []):
            src = e.get("from")
            tgt = e.get("to")
            if not src or not tgt:
                continue
            eid = stable_id("ie", f"{src}->{tgt}-{e.get('label','')}")
            cells.append(Cell(
                id=eid, value=esc(e.get("label", "")),
                style=ortho_edge_style(accent),
                parent="1", edge=True,
                source=src, target=tgt,
            ))

    # ── External edges ────────────────────────────────────────
    for layer in layers:
        src_accent = layer["accent"]
        src_idx    = idx_by_layer[layer["layer_name"]]
        for ext in layer.get("external_edges", []):
            src = ext.get("from")
            if not src:
                continue
            tgt_layer      = ext.get("to_layer", "")
            hint           = (ext.get("to_label_hint") or "").lower()
            tgt_candidates = all_node_ids_by_layer.get(tgt_layer, [])
            tgt_id: str | None = None
            if hint:
                for nid, lbl in tgt_candidates:
                    if hint in lbl.lower() or hint in nid.lower():
                        tgt_id = nid
                        break
            if not tgt_id and tgt_candidates:
                tgt_id = tgt_candidates[0][0]
            if not tgt_id:
                continue
            tgt_idx   = idx_by_layer.get(tgt_layer, src_idx + 1)
            src_above = src_idx < tgt_idx
            eid = stable_id("ee", f"{src}->{tgt_id}-{ext.get('label','')}")
            cells.append(Cell(
                id=eid, value=esc(ext.get("label", "")),
                style=ortho_edge_style(src_accent, src_above),
                parent="1", edge=True,
                source=src, target=tgt_id,
            ))

    # ── Legend ────────────────────────────────────────────────
    legend_x = page_w - left_margin - 220
    legend_y = top_margin
    cells.append(Cell(
        id="legend-box", value="",
        style=(
            "rounded=1;whiteSpace=wrap;html=1;"
            "fillColor=none;strokeColor=#CCCCCC;dashed=1;dashPattern=4 4;"
        ),
        parent="1", vertex=True,
        x=legend_x, y=legend_y,
        w=200, h=32 + len(layers) * 30,
    ))
    cells.append(Cell(
        id="legend-title", value="<b>LAYERS</b>",
        style=(
            "text;html=1;strokeColor=none;fillColor=none;"
            "align=left;fontColor=#555555;fontSize=10;"
        ),
        parent="1", vertex=True,
        x=legend_x + 10, y=legend_y + 6, w=180, h=18,
    ))
    for i, layer in enumerate(layers):
        accent = layer["accent"]
        cells.append(Cell(
            id=f"legend-{layer['layer_name']}",
            value=esc(layer["display_name"]),
            style=(
                f"rounded=1;whiteSpace=wrap;html=1;arcSize=6;"
                f"fillColor={light_fill(accent)};strokeColor={accent};strokeWidth=1;"
                f"fontColor=#333333;fontSize=9;"
            ),
            parent="1", vertex=True,
            x=legend_x + 10, y=legend_y + 28 + i * 30,
            w=180, h=22,
        ))

    page_h = top_margin + len(layers) * (grp_h + grp_gap) + 50
    return render_mxfile(
        cells, name="Detailed", page_w=page_w, page_h=page_h, background="#FFFFFF"
    )


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
    """One <diagram> element (not a full file)."""
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


def build_step_page(
    step: dict,
    step_num: int,
    total: int,
    next_step: dict | None,
    main_page_id: str,
    back_label: str = "← Overview",
    app_name: str = "the app",
) -> tuple[list[Cell], str, str, int, int]:
    """Build one detail page for a flow step.

    Returns (cells, page_name, page_id, page_w, page_h).
    """
    USER_COLOR = "#89B4FA"
    APP_COLOR  = "#A6E3A1"

    actor        = step.get("actor", "user")
    accent       = USER_COLOR if actor == "user" else APP_COLOR
    actor_label  = "YOU DO THIS" if actor == "user" else f"{app_name.upper()} DOES THIS"

    page_w = 1100
    box_w  = 920
    left_x = (page_w - box_w) // 2
    y      = 20

    cells: list[Cell] = []

    def add_section(cid: str, text: str) -> None:
        """Append separator rule + accent-colored section label; advances y."""
        nonlocal y
        cells.append(Cell(
            id=f"{cid}-rule", value="",
            style=(
                f"rounded=0;whiteSpace=wrap;html=1;"
                f"fillColor={PALETTE['muted']};strokeColor=none;opacity=30;"
            ),
            parent="1", vertex=True,
            x=left_x, y=y, w=box_w, h=1,
        ))
        cells.append(Cell(
            id=cid, value=f"<b>{esc(text)}</b>",
            style=(
                f"text;html=1;strokeColor=none;fillColor=none;"
                f"align=left;verticalAlign=middle;"
                f"fontColor={accent};fontSize=9;fontStyle=1;"
            ),
            parent="1", vertex=True,
            x=left_x, y=y + 6, w=box_w, h=18,
        ))
        y += 30

    # ── Nav row ────────────────────────────────────────────────
    cells.append(Cell(
        id="p-back", value=esc(back_label),
        style=(
            f"rounded=1;whiteSpace=wrap;html=1;arcSize=40;"
            f"fillColor={PALETTE['lane_bg']};strokeColor={PALETTE['muted']};"
            f"fontColor={PALETTE['text']};fontSize=11;"
        ),
        parent="1", vertex=True,
        x=left_x, y=y, w=130, h=30,
        link=f"data:page/id,{main_page_id}",
        tooltip="Return to the phase overview",
    ))
    cells.append(Cell(
        id="p-counter", value=esc(f"Step {step_num} of {total}"),
        style=(
            f"text;html=1;strokeColor=none;fillColor=none;align=left;"
            f"verticalAlign=middle;fontColor={PALETTE['muted']};fontSize=11;"
        ),
        parent="1", vertex=True,
        x=left_x + 146, y=y + 5, w=200, h=20,
    ))
    y += 40

    # ── Progress dots ──────────────────────────────────────────
    dot_size = 10
    dot_gap  = 8
    dots_w   = total * dot_size + (total - 1) * dot_gap
    dots_x   = (page_w - dots_w) // 2
    for d in range(total):
        current = (d + 1 == step_num)
        cells.append(Cell(
            id=f"p-dot-{d}", value="",
            style=(
                f"ellipse;whiteSpace=wrap;html=1;"
                f"fillColor={accent if current else PALETTE['muted']};strokeColor=none;"
                + ("shadow=1;" if current else "")
            ),
            parent="1", vertex=True,
            x=dots_x + d * (dot_size + dot_gap), y=y + 2,
            w=dot_size, h=dot_size,
        ))
    y += 26

    # ── Actor banner ──────────────────────────────────────────
    cells.append(Cell(
        id="p-actor", value=f"<b>{actor_label}</b>",
        style=(
            f"rounded=1;whiteSpace=wrap;html=1;arcSize=6;"
            f"fillColor={accent};gradientColor={darker(accent)};gradientDirection=east;"
            f"strokeColor=none;"
            f"fontColor={PALETTE['canvas']};fontSize=13;fontStyle=1;"
        ),
        parent="1", vertex=True,
        x=left_x, y=y, w=box_w, h=40,
    ))
    y += 52

    # ── Title ─────────────────────────────────────────────────
    cells.append(Cell(
        id="p-title", value=f"<b>{esc(step['label'])}</b>",
        style=(
            f"rounded=1;whiteSpace=wrap;html=1;arcSize=8;shadow=1;"
            f"fillColor={PALETTE['canvas']};strokeColor={accent};strokeWidth=2.5;"
            f"fontColor={PALETTE['text']};fontSize=17;"
        ),
        parent="1", vertex=True,
        x=left_x, y=y, w=box_w, h=68,
    ))
    y += 80

    # ── About this step ───────────────────────────────────────
    description = step.get("description") or step.get("detail", "")
    if description:
        add_section("p-sec-about", "ABOUT THIS STEP")
        desc_h = max(60, (len(description) // 80 + 1) * 22)
        cells.append(Cell(
            id="p-desc", value=esc(description),
            style=(
                f"text;html=1;strokeColor=none;fillColor=none;"
                f"align=left;verticalAlign=top;whiteSpace=wrap;"
                f"fontColor={PALETTE['text']};fontSize=13;"
            ),
            parent="1", vertex=True,
            x=left_x, y=y, w=box_w, h=desc_h,
        ))
        y += desc_h + 16

    # ── What you'll see — blockquote-style callout ────────────
    what_you_see = step.get("what_you_see")
    if what_you_see:
        add_section("p-sec-wys", "WHAT YOU'LL SEE")
        wys_h = max(52, (len(what_you_see) // 78 + 1) * 24 + 12)
        # Accent left bar
        cells.append(Cell(
            id="p-wys-bar", value="",
            style=f"rounded=0;whiteSpace=wrap;html=1;fillColor={accent};strokeColor=none;",
            parent="1", vertex=True,
            x=left_x, y=y, w=5, h=wys_h,
        ))
        # Callout text (no border — bar carries the visual weight)
        cells.append(Cell(
            id="p-wys", value=esc(what_you_see),
            style=(
                f"text;html=1;strokeColor=none;"
                f"fillColor={PALETTE['lane_bg']};"
                f"align=left;verticalAlign=middle;whiteSpace=wrap;"
                f"fontColor={PALETTE['text']};fontSize=13;fontStyle=2;"
                f"spacingLeft=12;spacingRight=12;"
            ),
            parent="1", vertex=True,
            x=left_x + 5, y=y, w=box_w - 5, h=wys_h,
        ))
        y += wys_h + 16

    # ── Tips ─────────────────────────────────────────────────
    tips = step.get("tips", [])
    if tips:
        add_section("p-sec-tips", "TIPS")
        for tip in tips:
            # Accent dot marker
            cells.append(Cell(
                id=stable_id("p-tip-dot", tip),
                value="",
                style=(
                    f"ellipse;whiteSpace=wrap;html=1;"
                    f"fillColor={accent};strokeColor=none;"
                ),
                parent="1", vertex=True,
                x=left_x + 11, y=y + 14, w=10, h=10,
            ))
            cells.append(Cell(
                id=stable_id("p-tip", tip),
                value=esc(tip),
                style=(
                    f"rounded=1;whiteSpace=wrap;html=1;arcSize=6;"
                    f"fillColor={PALETTE['lane_bg']};strokeColor=none;"
                    f"fontColor={PALETTE['text']};fontSize=12;"
                    f"align=left;spacingLeft=32;verticalAlign=middle;"
                ),
                parent="1", vertex=True,
                x=left_x, y=y, w=box_w, h=38,
            ))
            y += 46

    y += 20

    # ── Next step button ─────────────────────────────────────
    if next_step:
        next_actor  = next_step.get("actor", "user")
        next_accent = USER_COLOR if next_actor == "user" else APP_COLOR
        cells.append(Cell(
            id="p-next",
            value=f"Next: {esc(next_step['label'])} →",
            style=(
                f"rounded=1;whiteSpace=wrap;html=1;arcSize=40;shadow=1;"
                f"fillColor={next_accent};gradientColor={darker(next_accent)};gradientDirection=east;"
                f"strokeColor=none;"
                f"fontColor={PALETTE['canvas']};fontSize=13;fontStyle=1;"
            ),
            parent="1", vertex=True,
            x=left_x, y=y, w=box_w, h=48,
            link=f"data:page/id,{next_step['id']}",
            tooltip=f"Go to: {next_step['label']}",
        ))
        y += 60

    page_name = f"Step {step_num}: {step['label'][:38]}"
    return cells, page_name, step["id"], page_w, y + 36


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", help="Path to spec JSON (default: stdin)")
    ap.add_argument("--out-portfolio", required=True)
    ap.add_argument("--out-detailed", required=True)
    ap.add_argument(
        "--out-journey",
        help=(
            "Optional third diagram: multi-page interactive user journey for "
            "non-technical audiences. Requires 'phases' and/or 'user_flow' in spec."
        ),
    )
    args = ap.parse_args()

    if args.spec:
        spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    else:
        spec = json.loads(sys.stdin.read())

    # Fill in layer short-codes where missing (for id prefixing convention)
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
