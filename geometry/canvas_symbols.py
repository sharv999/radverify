"""
canvas_symbols.py

Vector drawing helpers for the Room Design canvas.

Patch note:
- Tkinter Canvas.create_arc does NOT support arrow="last".
- draw_rotation_indicator therefore draws the arc and adds a small polygon
  arrowhead manually.
"""

from __future__ import annotations

import math
from typing import Tuple


NM_PATIENT_OFFSET_M = 0.5


def draw_radiation_symbol(canvas, x, y, r=18):
    """
    Draw a clean trefoil radiation symbol:
    - yellow circular background
    - three black blades
    - central black disk
    """

    import math

    # Background
    bg_r = r * 1.25
    canvas.create_oval(
        x - bg_r, y - bg_r,
        x + bg_r, y + bg_r,
        fill="#facc15",
        outline="#111111",
        width=1,
        tags=("radiation_symbol",),
    )

    # Trefoil blades
    inner_r = r * 0.42
    outer_r = r * 1.05
    blade_half_angle = math.radians(28)

    # Standard trefoil orientation: one blade down, two upper
    for angle_deg in (-90, 30, 150):
        a = math.radians(angle_deg)

        points = []

        # Outer arc approximation
        for i in range(12):
            t = -blade_half_angle + (2 * blade_half_angle) * i / 11
            aa = a + t
            points.append((
                x + outer_r * math.cos(aa),
                y + outer_r * math.sin(aa),
            ))

        # Inner arc back
        for i in range(11, -1, -1):
            t = -blade_half_angle + (2 * blade_half_angle) * i / 11
            aa = a + t
            points.append((
                x + inner_r * math.cos(aa),
                y + inner_r * math.sin(aa),
            ))

        canvas.create_polygon(
            points,
            fill="#000000",
            outline="#000000",
            tags=("radiation_symbol",),
        )

    # Central disk
    c_r = r * 0.28
    canvas.create_oval(
        x - c_r, y - c_r,
        x + c_r, y + c_r,
        fill="#000000",
        outline="#000000",
        tags=("radiation_symbol",),
    )


def draw_rotation_indicator(canvas, cx: float, cy: float, r: float = 22, tag: str = "source_symbol") -> None:
    """
    Draw a CT rotation cue.

    Tkinter create_arc does not accept arrow="last", so this uses:
      1. create_arc(... style="arc")
      2. a small triangular arrowhead at the approximate arc end.
    """
    outline = "#2563eb"

    start_deg = 30
    extent_deg = 300
    end_deg = start_deg + extent_deg

    canvas.create_arc(
        cx - r,
        cy - r,
        cx + r,
        cy + r,
        start=start_deg,
        extent=extent_deg,
        style="arc",
        outline=outline,
        width=2,
        tags=(tag,),
    )

    # Tk angles: 0 deg is +x axis, positive is counter-clockwise.
    # Canvas y increases downwards, so y uses -sin.
    theta = math.radians(end_deg)
    tip_x = cx + r * math.cos(theta)
    tip_y = cy - r * math.sin(theta)

    # Tangent direction for counter-clockwise arc.
    tangent = theta + math.pi / 2
    head_len = 7
    head_half_width = 4

    back_x = tip_x - head_len * math.cos(tangent)
    back_y = tip_y + head_len * math.sin(tangent)

    normal = tangent + math.pi / 2
    p1 = (tip_x, tip_y)
    p2 = (
        back_x + head_half_width * math.cos(normal),
        back_y - head_half_width * math.sin(normal),
    )
    p3 = (
        back_x - head_half_width * math.cos(normal),
        back_y + head_half_width * math.sin(normal),
    )

    canvas.create_polygon(
        p1[0], p1[1],
        p2[0], p2[1],
        p3[0], p3[1],
        fill=outline,
        outline=outline,
        tags=(tag,),
    )


def nm_patient_point(
    cx: float,
    cy: float,
    px_per_m: float,
    scanner_rotation_deg: float = 0.0,
    offset_m: float = NM_PATIENT_OFFSET_M,
) -> Tuple[float, float]:
    offset_px = float(offset_m) * px_per_m
    theta = math.radians(scanner_rotation_deg)
    return (
        cx + offset_px * math.cos(theta),
        cy + offset_px * math.sin(theta),
    )


def draw_nm_patient_icon(
    canvas,
    cx: float,
    cy: float,
    px_per_m: float,
    scanner_rotation_deg: float = 0.0,
    tag: str = "nm_patient_symbol",
    offset_m: float = NM_PATIENT_OFFSET_M,
    label_offset_px: float = 20.0,
    label: str = "NM",
) -> Tuple[float, float]:
    px, py = nm_patient_point(
        cx, cy, px_per_m, scanner_rotation_deg, offset_m=offset_m
    )

    outline = "#dc2626"
    y_scale = 0.8
    icon_scale = 1.2

    def sy(offset_y: float) -> float:
        return py + (offset_y * y_scale * icon_scale)

    # Draw a larger, more human-like patient outline while keeping the
    # canonical source point fixed at (px, py) so the radiation symbol and
    # barrier physics overlays remain aligned. The N-S dimension is slightly
    # compressed to better match a standing-body silhouette on the canvas.
    head_r = 9.0 * icon_scale
    head_cy = sy(-30.0)

    left_outline = (
        px - (4.0 * icon_scale), head_cy + (8.0 * y_scale * icon_scale),
        px - (7.0 * icon_scale), sy(-20.0),
        px - (17.0 * icon_scale), sy(-15.0),
        px - (23.0 * icon_scale), sy(-4.0),
        px - (24.0 * icon_scale), sy(10.0),
        px - (22.0 * icon_scale), sy(24.0),
        px - (18.0 * icon_scale), sy(38.0),
        px - (21.0 * icon_scale), sy(52.0),
        px - (18.0 * icon_scale), sy(49.0),
        px - (15.0 * icon_scale), sy(40.0),
        px - (12.0 * icon_scale), sy(17.0),
        px - (10.0 * icon_scale), sy(3.0),
        px - (8.0 * icon_scale), sy(16.0),
        px - (8.0 * icon_scale), sy(30.0),
        px - (10.0 * icon_scale), sy(50.0),
        px - (10.0 * icon_scale), sy(72.0),
        px - (7.0 * icon_scale), sy(92.0),
        px - (5.0 * icon_scale), sy(112.0),
        px - (5.0 * icon_scale), sy(132.0),
        px - (7.0 * icon_scale), sy(150.0),
        px - (11.0 * icon_scale), sy(162.0),
        px - (8.0 * icon_scale), sy(166.0),
        px - (2.0 * icon_scale), sy(166.0),
    )
    right_outline = (
        px + (4.0 * icon_scale), head_cy + (8.0 * y_scale * icon_scale),
        px + (7.0 * icon_scale), sy(-20.0),
        px + (17.0 * icon_scale), sy(-15.0),
        px + (23.0 * icon_scale), sy(-4.0),
        px + (24.0 * icon_scale), sy(10.0),
        px + (22.0 * icon_scale), sy(24.0),
        px + (18.0 * icon_scale), sy(38.0),
        px + (21.0 * icon_scale), sy(52.0),
        px + (18.0 * icon_scale), sy(49.0),
        px + (15.0 * icon_scale), sy(40.0),
        px + (12.0 * icon_scale), sy(17.0),
        px + (10.0 * icon_scale), sy(3.0),
        px + (8.0 * icon_scale), sy(16.0),
        px + (8.0 * icon_scale), sy(30.0),
        px + (10.0 * icon_scale), sy(50.0),
        px + (10.0 * icon_scale), sy(72.0),
        px + (7.0 * icon_scale), sy(92.0),
        px + (5.0 * icon_scale), sy(112.0),
        px + (5.0 * icon_scale), sy(132.0),
        px + (7.0 * icon_scale), sy(150.0),
        px + (11.0 * icon_scale), sy(162.0),
        px + (8.0 * icon_scale), sy(166.0),
        px + (2.0 * icon_scale), sy(166.0),
    )
    left_inner_leg = (
        px - (2.0 * icon_scale), sy(72.0),
        px - (1.0 * icon_scale), sy(96.0),
        px - (1.0 * icon_scale), sy(122.0),
        px - (3.0 * icon_scale), sy(150.0),
        px - (1.5 * icon_scale), sy(162.0),
    )
    right_inner_leg = (
        px + (2.0 * icon_scale), sy(72.0),
        px + (1.0 * icon_scale), sy(96.0),
        px + (1.0 * icon_scale), sy(122.0),
        px + (3.0 * icon_scale), sy(150.0),
        px + (1.5 * icon_scale), sy(162.0),
    )

    canvas.create_oval(
        px - head_r,
        head_cy - head_r,
        px + head_r,
        head_cy + head_r,
        fill="",
        outline=outline,
        width=2,
        tags=(tag,),
    )
    canvas.create_line(
        *left_outline,
        fill=outline,
        width=2,
        smooth=True,
        splinesteps=24,
        tags=(tag,),
    )
    canvas.create_line(
        *right_outline,
        fill=outline,
        width=2,
        smooth=True,
        splinesteps=24,
        tags=(tag,),
    )
    canvas.create_line(
        *left_inner_leg,
        fill=outline,
        width=2,
        smooth=True,
        splinesteps=24,
        tags=(tag,),
    )
    canvas.create_line(
        *right_inner_leg,
        fill=outline,
        width=2,
        smooth=True,
        splinesteps=24,
        tags=(tag,),
    )

    marker_label = str(label or "").strip()
    if marker_label:
        canvas.create_text(
            px,
            py - float(label_offset_px) * icon_scale,
            text=marker_label,
            fill="#dc2626",
            font=("Segoe UI", 8, "bold"),
            tags=(tag,),
        )
    return px, py


def draw_one_m_circle(
    canvas,
    cx: float,
    cy: float,
    px_per_m: float,
    label: str,
    tag: str = "one_m_circle",
    radius_m: float = 1.0,
    label_gap_px: float = 10.0,
) -> None:
    r = float(radius_m) * px_per_m
    canvas.create_oval(
        cx - r,
        cy - r,
        cx + r,
        cy + r,
        outline="#dc2626",
        width=2,
        dash=(7, 5),
        tags=(tag),
    )

    if str(label or "").strip():
        # Match the PDF rendition: place the source-distance annotation
        # horizontally centred just above the 1 m contour, not inside it.
        canvas.create_text(
            cx,
            cy - r - float(label_gap_px),
            text=label,
            fill="#dc2626",
            font=("Segoe UI", 8, "bold"),
            anchor="center",
            tags=(tag,),
        )


def draw_xray_machine_icon(
    canvas, cx: float, cy: float, rotation_deg: float = 0.0,
    scale: float = 40.0, tag: str = "xray_machine_symbol",
) -> None:
    """Plain table + tube schematic; tube is 1.2 m from table centre."""
    theta = math.radians(rotation_deg)
    def rot(x, y):
        return (cx + x*math.cos(theta)-y*math.sin(theta),
                cy + x*math.sin(theta)+y*math.cos(theta))
    def line(x0,y0,x1,y1,**kw): canvas.create_line(*rot(x0,y0),*rot(x1,y1),tags=(tag,),**kw)
    def rect(x0,y0,x1,y1,**kw):
        pts=[rot(x0,y0),rot(x1,y0),rot(x1,y1),rot(x0,y1)]
        canvas.create_polygon([v for pt in pts for v in pt],tags=(tag,),**kw)
    hl=max(32.0,0.9*scale); hw=max(13.0,0.35*scale); d=1.2*scale
    line(-hl-28,0,hl+28,0,fill="#1e3a8a",dash=(5,3),width=1)
    line(0,-d-24,0,hw+24,fill="#475569",dash=(5,3),width=1)
    rect(-hl,-hw,hl,hw,outline="#111827",fill="",width=2)
    rect(-0.32*scale,-0.07*scale,0.32*scale,0.07*scale,outline="#111827",fill="",width=1)
    ty=-d
    rect(-0.20*scale,ty-0.10*scale,0.20*scale,ty+0.10*scale,outline="#111827",fill="",width=2)
    # Reference convention: triangle apex points back toward the tube housing.
    pts=[rot(-0.12*scale,ty+0.30*scale),rot(0.12*scale,ty+0.30*scale),rot(0,ty+0.10*scale)]
    canvas.create_polygon([v for pt in pts for v in pt],outline="#1e3a8a",fill="",width=2,tags=(tag,))
def draw_wall_bucky(canvas, x: float, y: float, width_px: float = 32, height_px: float = 54, tag: str = "wall_bucky") -> None:
    """Plain thin chest-bucky symbol matching the user's reference sketch."""
    canvas.create_rectangle(x-width_px*0.10,y-height_px/2,x+width_px*0.10,y+height_px/2,
                            outline="#111827",fill="",width=2,tags=(tag,))


def draw_chest_bucky_tube_combo(canvas, bucky_x: float, bucky_y: float, wall: str, scale: float,
                                 distance_m: float = 2.5, tag: str = "chest_bucky_combo") -> None:
    """Simple optional chest-bucky + tube schematic matching the reference sketch."""
    wall = str(wall or "N").upper()
    ix, iy = {"N": (0, 1), "S": (0, -1), "E": (-1, 0), "W": (1, 0)}[wall]
    px, py = -iy, ix
    tx = bucky_x + ix * distance_m * scale
    ty = bucky_y + iy * distance_m * scale

    # Fine dash-dot centreline through the bucky and tube. It extends 0.5 m
    # beyond the tube on the tube side, matching the reference sketch.
    bucky_side_extension = 0.10 * scale
    tube_side_extension = 0.50 * scale
    canvas.create_line(
        bucky_x - ix * bucky_side_extension, bucky_y - iy * bucky_side_extension,
        tx + ix * tube_side_extension, ty + iy * tube_side_extension,
        fill="#475569", dash=(6, 3, 1, 3), width=1, tags=(tag,),
    )

    def oriented_rect(cx, cy, half_along, half_normal):
        pts = []
        for along, normal in [(-half_along, -half_normal), (half_along, -half_normal),
                              (half_along, half_normal), (-half_along, half_normal)]:
            pts.extend((cx + px*along + ix*normal, cy + py*along + iy*normal))
        canvas.create_polygon(pts, outline="#111827", fill="", width=2, tags=(tag,))

    # Reference convention: the small rear plate touches the room wall, and
    # the taller bucky rectangle sits immediately in front of it (room side).
    # ``bucky_x/y`` is the wall face, so this remains exact for N/E/S/W walls.
    rear_half_normal = 0.06 * scale
    rear_cx = bucky_x + ix * rear_half_normal
    rear_cy = bucky_y + iy * rear_half_normal
    oriented_rect(rear_cx, rear_cy, 0.13 * scale, rear_half_normal)

    stand_half_along = 0.28 * scale
    stand_half_normal = 0.04 * scale
    stand_cx = bucky_x + ix * (2.0 * rear_half_normal + stand_half_normal)
    stand_cy = bucky_y + iy * (2.0 * rear_half_normal + stand_half_normal)
    oriented_rect(stand_cx, stand_cy, stand_half_along, stand_half_normal)

    # Tube housing sits beyond the triangle, away from the bucky.
    housing_cx = tx + ix * 0.20 * scale
    housing_cy = ty + iy * 0.20 * scale
    oriented_rect(housing_cx, housing_cy, 0.18 * scale, 0.10 * scale)

    # Triangle wide side faces the bucky; apex points toward the tube housing.
    base_cx = tx - ix * 0.12 * scale
    base_cy = ty - iy * 0.12 * scale
    b1 = (base_cx + px * 0.14 * scale, base_cy + py * 0.14 * scale)
    b2 = (base_cx - px * 0.14 * scale, base_cy - py * 0.14 * scale)
    apex = (tx + ix * 0.08 * scale, ty + iy * 0.08 * scale)
    canvas.create_polygon([*b1, *b2, *apex], outline="#1e3a8a", fill="", width=2, tags=(tag,))
