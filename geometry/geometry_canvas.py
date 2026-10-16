from __future__ import annotations

import re

import tkinter as tk

from PIL.ImageOps import scale
from config.ui_constants import *

from geometry.geometry_model import RoomGeometry, Opening, WallBucky, BuckyShield, ControlWall
from geometry.canvas_symbols import (
    draw_radiation_symbol,
    draw_nm_patient_icon,
    draw_one_m_circle,
    draw_xray_machine_icon,
    draw_wall_bucky,
    draw_chest_bucky_tube_combo,
)
from geometry.source_marker_layout import resolve_source_marker_points

DESIGN_FIELD_WIDTH_M = 12.0
DESIGN_FIELD_HEIGHT_M = 8.0
CANVAS_MARGIN_PX = 48


def _format_marker_activity(value: object) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return ""
    if numeric <= 0:
        return ""
    return f"{numeric:g} MBq"


def _format_isotope_label(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    match = re.fullmatch(r"([A-Za-z]+)-?(\d+[A-Za-z]*)", text)
    if not match:
        return text
    element, mass = match.groups()
    return f"{element}-{mass}"


def _resolve_patient_canvas_label(rendering: dict[str, object], render_metadata: dict[str, object]) -> str:
    fallback = str(rendering.get("patient_marker_label", "NM") or "").strip()
    isotope = _format_isotope_label(render_metadata.get("radionuclide"))
    if not isotope:
        return fallback

    activity = _format_marker_activity(
        render_metadata.get("injected_activity_mbq", render_metadata.get("administered_activity_mbq"))
    )
    if activity:
        return f"{isotope} {activity}"
    return isotope


class GeometryCanvas(tk.Canvas):

    def __init__(self, master, width=620, height=460, **kwargs):
        super().__init__(
            master,
            width=width,
            height=height,
            bg=COLOUR_CANVAS_BG,
            highlightthickness=1,
            highlightbackground="#cccccc",
            **kwargs,
        )
        self.margin = 55


    def draw_room(self, geom: RoomGeometry, source_type: str | None = None, ksec_label: str | None = None, scanner_label: str | None = None, wall_t_values: dict | None = None, layout_rendering: dict | None = None) -> None:
        self.delete("all")
        geom.clamp_source_inside_room()

        canvas_w = self.winfo_width()
        canvas_h = self.winfo_height()

        if canvas_w <= 1:
            canvas_w = int(float(self["width"]))
        if canvas_h <= 1:
            canvas_h = int(float(self["height"]))

        if geom.length_m <= 0 or geom.width_m <= 0:
            self.create_text(canvas_w / 2, canvas_h / 2, text="Enter valid room dimensions", fill=COLOUR_ALERT, font=FONT_12_BOLD)
            return

        available_w = max(100, canvas_w - 2 * self.margin)
        available_h = max(100, canvas_h - 2 * self.margin - TOP_PADDING_PX)

        canvas_w = max(self.winfo_width(), 1)
        canvas_h = max(self.winfo_height(), 1)

        usable_w = max(canvas_w - CANVAS_MARGIN_PX * 2, 1)
        usable_h = max(canvas_h - CANVAS_MARGIN_PX * 2, 1)

        scale = min(
            usable_w / DESIGN_FIELD_WIDTH_M,
            usable_h / DESIGN_FIELD_HEIGHT_M,
        )

        room_w_px = float(geom.width_m) * scale
        room_h_px = float(geom.length_m) * scale

        field_w_px = DESIGN_FIELD_WIDTH_M * scale
        field_h_px = DESIGN_FIELD_HEIGHT_M * scale

        field_x0 = (canvas_w - field_w_px) / 2
        field_y0 = (canvas_h - field_h_px) / 2

        x0 = field_x0 + (field_w_px - room_w_px) / 2
        y0 = field_y0 + (field_h_px - room_h_px) / 2
        x1 = x0 + room_w_px
        y1 = y0 + room_h_px

        def map_point(x_m: float, y_m: float):
            x = x0 + x_m * scale
            y = y1 - y_m * scale
            return x, y

        self._draw_one_m_grid(
            field_x0,
            field_y0,
            field_x0 + field_w_px,
            field_y0 + field_h_px,
            scale,
            geom,
        )
        self.create_rectangle(x0, y0, x1, y1, outline=COLOUR_OUTLINE, width=ROOM_OUTLINE_WIDTH, tags=("room_outline",))

        wall_t_values = wall_t_values or {}

        wall_material_labels = getattr(geom, "wall_material_labels", {}) or {}
        wall_p_values = getattr(geom, "wall_p_values", {}) or {}
        wall_distance_values = getattr(geom, "wall_distance_values", {}) or {}
        wall_role_labels = getattr(geom, "wall_role_labels", {}) or {}
        dose_labels = getattr(geom, "barrier_dose_label_map", {}) or {}
        wall_t_values = wall_t_values or {}

        cx = (x0 + x1) / 2
        cy = (y0 + y1) / 2

        dose_labels = getattr(geom, "barrier_dose_label_map", {}) or {}

        risk_map = getattr(geom, "barrier_risk_map", {}) or {}
        show_barrier_status_text = bool((layout_rendering or {}).get("show_barrier_status_text", True))

        self._draw_wall_labels(
            "N",
            cx,
            y0,
            wall_t_values,
            wall_material_labels,
            dose_labels,
            wall_p_values,
            role_labels=wall_role_labels,
            fill=self._risk_colour_for_barrier(risk_map, "N wall"),
            status=self._risk_status_for_barrier(risk_map, "N wall") if show_barrier_status_text else "",
        )

        self._draw_wall_labels(
            "S",
            cx,
            y1,
            wall_t_values,
            wall_material_labels,
            dose_labels,
            wall_p_values,
            role_labels=wall_role_labels,
            fill=self._risk_colour_for_barrier(risk_map, "S wall"),
            status=self._risk_status_for_barrier(risk_map, "S wall") if show_barrier_status_text else "",
        )

        self._draw_wall_labels(
            "E",
            x1,
            cy,
            wall_t_values,
            wall_material_labels,
            dose_labels,
            wall_p_values,
            role_labels=wall_role_labels,
            fill=self._risk_colour_for_barrier(risk_map, "E wall"),
            status=self._risk_status_for_barrier(risk_map, "E wall") if show_barrier_status_text else "",
        )

        self._draw_wall_labels(
            "W",
            x0,
            cy,
            wall_t_values,
            wall_material_labels,
            dose_labels,
            wall_p_values,
            role_labels=wall_role_labels,
            fill=self._risk_colour_for_barrier(risk_map, "W wall"),
            status=self._risk_status_for_barrier(risk_map, "W wall") if show_barrier_status_text else "",
        )

        self._draw_floor_ceiling_labels(
            field_x0,
            field_y0,
            field_w_px,
            scale,
            wall_t_values,
            wall_material_labels,
            dose_labels,
            wall_p_values,
            wall_distance_values,
            risk_map,
            role_labels=wall_role_labels,
            show_status_text=show_barrier_status_text,
        )

        self._draw_room_title(
            geom,
            field_x0 + 12,
            field_y0 + field_h_px - 46,
        )

        canvas_w = self.winfo_width()
        canvas_h = self.winfo_height()

        # Bottom-right architectural scale bar, right-justified to the fixed design grid.
        scale_metres = 2
        scale_padding_bottom = 26

        # Align the 0 and 2 m ticks with the 1 m grid.  This moves the scale
        # marker 0.2 m right relative to the previous 18 px inset at the
        # standard canvas scale.
        scale_x = field_x0 + field_w_px - (scale_metres * scale)
        scale_y = field_y0 + field_h_px - scale_padding_bottom

        # Keep the legend visibly separate from the scale marker (about 5 mm clear).
        self._draw_status_legend(
            scale_x,
            scale_y - 55,
        )

        self.create_text(
            scale_x,
            scale_y - 8,
            text="Scale: 1 m",
            anchor="sw",
            fill=COLOUR_TEXT_MUTED,
            font=FONT_8,
            tags=("scale_marker", "room_scale_label"),
        )

        self._draw_scale_marker(scale_x, scale_y, scale, metres=scale_metres)

        for opening_index, opening in enumerate(geom.openings, start=1):
            self._draw_opening(opening, geom, map_point, scale, opening_index)

        if getattr(geom, "wall_bucky", None):
            self._draw_wall_bucky(geom.wall_bucky, geom, map_point, scale)
        if getattr(geom, "control_wall", None):
            self._draw_control_wall(geom.control_wall, geom, map_point, scale)
        if getattr(geom, "wall_bucky", None):
            self._draw_gxr_bucky_beam_envelope(geom, map_point)

        sx, sy = map_point(geom.source.x_m, geom.source.y_m)
        rotation = int(getattr(geom.source, "rotation_deg", 0) or 0) % 360
        rendering = dict(layout_rendering or {})
        render_metadata = dict(getattr(geom.source, "render_metadata", {}) or {})
        marker_points = resolve_source_marker_points(sx, sy, scale, rotation, rendering)
        symbol_kind = str(rendering.get("source_symbol_kind", "point_source") or "point_source")
        if symbol_kind == "xray_machine":
            # Fixed GXR table orientation: tube north, primary beam south.
            draw_xray_machine_icon(self, *marker_points.source, rotation_deg=0, scale=scale)
            self._draw_gxr_table_beam_footprint(*marker_points.source, 0, scale)
        if bool(rendering.get("show_radiation_symbol", True)):
            draw_radiation_symbol(self, *marker_points.radiation, r=15)
        if bool(rendering.get("show_patient_symbol", False)):
            draw_nm_patient_icon(
                self,
                *marker_points.source,
                scale,
                scanner_rotation_deg=rotation,
                offset_m=float(rendering.get("patient_symbol_offset_m", 0.5) or 0.0),
                label_offset_px=float(rendering.get("patient_label_offset_px", 20.0) or 0.0),
                label=_resolve_patient_canvas_label(rendering, render_metadata),
            )

        if scanner_label:
            self.create_text(
                marker_points.source[0],
                marker_points.source[1] + 34,
                text=str(scanner_label),
                fill=COLOUR_TEXT_MUTED,
                font=FONT_8_BOLD,
                tags=("scanner_label",),
            )

        label = None
        rx, ry = marker_points.reference_circle
        # -------------------------------------------------
        # CT / scatter workload annotation
        # -------------------------------------------------
        # The canvas call path no longer passes a separate ksec_label.
        # Geometry-tab sync writes CT source values onto geom.source before
        # drawing, so derive the same weekly 1 m annotation directly from the
        # geometry source.  This keeps the canvas aligned with the PDF room
        # rendition and prevents the red label from disappearing.
        one_m_label = ""
        try:
            source = geom.source
            render_metadata = render_metadata or getattr(source, "render_metadata", {}) or {}

            ksec = float(render_metadata.get("ksec_mGy_per_100mAs_at_1m", 0.0) or 0.0)
            scans = float(render_metadata.get("scans_per_week", 0.0) or 0.0)
            workload = float(render_metadata.get("workload_mAs_per_scan", 0.0) or 0.0)

            if ksec > 0 and scans > 0 and workload > 0:
                weekly_scatter_mGy = ksec * (workload / 100.0) * scans
                weekly_scatter_uSv = weekly_scatter_mGy * 1000.0
                one_m_label = f"{weekly_scatter_uSv:.0f} µSv/wk @ 1 m"
        except Exception:
            one_m_label = ""

        if not one_m_label:
            one_m_label = str(ksec_label or "").strip()

        # Draw the same dashed 1 m source-distance contour and label placement
        # used by the PDF room-layout rendition.
        if bool(rendering.get("show_one_m_circle", True)):
            draw_one_m_circle(
                self, rx, ry, scale, one_m_label,
                radius_m=float(rendering.get("reference_circle_radius_m", 1.0) or 1.0),
                label_gap_px=float(rendering.get("reference_circle_label_gap_px", 10.0) or 0.0),
            )


    def _draw_one_m_grid(
        self,
        field_x0: float,
        field_y0: float,
        field_x1: float,
        field_y1: float,
        scale: float,
        geom: RoomGeometry,
    ) -> None:

        if scale <= 0:
            return

        minor_step = scale * 0.2
        major_step = scale

        # Vertical lines
        x = field_x0
        major_index = 0

        while x <= field_x1 + 0.5:

            self.create_line(
                x,
                field_y0,
                x,
                field_y1,
                fill=COLOUR_GRID_MAJOR if major_index % 1 == 0 else COLOUR_GRID_MINOR,
                width=2 if major_index % 1 == 0 else 1,
                tags=("room_grid",),
            )

            # Minor subdivisions
            if x + major_step <= field_x1:
                for i in range(1, 5):
                    mx = x + i * minor_step

                    if mx >= field_x1:
                        break

                    self.create_line(
                        mx,
                        field_y0,
                        mx,
                        field_y1,
                        fill=COLOUR_GRID_MINOR,
                        width=1,
                        tags=("room_grid",),
                    )

            x += major_step
            major_index += 1

        # Horizontal lines
        y = field_y0
        major_index = 0

        while y <= field_y1 + 0.5:

            self.create_line(
                field_x0,
                y,
                field_x1,
                y,
                fill=COLOUR_GRID_MAJOR if major_index % 1 == 0 else COLOUR_GRID_MINOR,
                width=2 if major_index % 1 == 0 else 1,
                tags=("room_grid",),
            )

            if y + major_step <= field_y1:
                for i in range(1, 5):
                    my = y + i * minor_step

                    if my >= field_y1:
                        break

                    self.create_line(
                        field_x0,
                        my,
                        field_x1,
                        my,
                        fill=COLOUR_GRID_MINOR,
                        width=1,
                        tags=("room_grid",),
                    )

            y += major_step
            major_index += 1


    def _draw_status_legend(self, x: float, y: float) -> None:
        self.create_text(
            x,
            y,
            text="Legend",
            anchor="sw",
            fill=COLOUR_TEXT_MUTED,
            font=FONT_8,
            tags=("status_legend", "status_legend_heading"),
        )

        items = [
            ("PASS", COLOUR_PASS),
            ("REVIEW", COLOUR_REVIEW_DARK),
            ("FAIL", COLOUR_FAIL),
        ]
        item_y = y + 16
        box_size = 8
        cursor_x = x
        text_gap = 4
        item_gap = 18

        for label, colour in items:
            self.create_rectangle(
                cursor_x,
                item_y - box_size + 1,
                cursor_x + box_size,
                item_y + 1,
                fill=colour,
                outline=colour,
                tags=("status_legend", f"status_legend_{label.lower()}"),
            )
            self.create_text(
                cursor_x + box_size + text_gap,
                item_y,
                text=label,
                anchor="sw",
                fill=COLOUR_TEXT,
                font=FONT_8_BOLD,
                tags=("status_legend", f"status_legend_{label.lower()}_label"),
            )
            bbox = self.bbox(f"status_legend_{label.lower()}_label")
            label_width = max(0, (bbox[2] - bbox[0])) if bbox else len(label) * 7
            cursor_x += box_size + text_gap + label_width + item_gap


    def _draw_room_title(self, geom: RoomGeometry, x: float, y: float) -> None:
        title = str(getattr(geom, "room_name", "") or "Room")
        height = float(getattr(geom, "height_m", 0.0) or 0.0)

        self.create_text(
            x,
            y,
            text=title,
            anchor="sw",
            fill=COLOUR_TEXT,
            font=FONT_11_BOLD,
            tags=("room_title",),
        )

        self.create_text(
            x,
            y + 18,
            text=f"FFL to FCL: {height:.2f} m",
            anchor="sw",
            fill=COLOUR_TEXT_MUTED,
            font=FONT_8,
            tags=("room_height_label",),
        )


    def _draw_scale_marker(
        self,
        x: float,
        y: float,
        scale: float,
        metres: int = 5,
    ) -> None:
        """
        Draw a right-justified architectural alternating scale bar.

        x, y define the left/top origin of the scale bar.
        Each segment represents 1 metre.
        """

        if scale <= 0 or metres <= 0:
            return

        bar_h = 7
        tick_h = 5
        number_y = y + bar_h + 13

        total_w = metres * scale

        # Alternating black/white bar segments.
        for i in range(metres):
            x0 = x + i * scale
            x1 = x + (i + 1) * scale

            fill = COLOUR_TEXT if i % 2 == 0 else COLOUR_CANVAS_BG

            self.create_rectangle(
                x0,
                y,
                x1,
                y + bar_h,
                fill=fill,
                outline=COLOUR_TEXT,
                width=1,
                tags=("scale_marker",),
            )

        # Tick marks and numbers.
        for i in range(metres + 1):
            tx = x + i * scale

            self.create_line(
                tx,
                y + bar_h,
                tx,
                y + bar_h + tick_h,
                fill=COLOUR_TEXT,
                width=1,
                tags=("scale_marker",),
            )

            self.create_text(
                tx,
                number_y,
                text=str(i),
                fill=COLOUR_TEXT,
                font=FONT_7,
                anchor="n",
                tags=("scale_marker",),
            )

        # Unit label.
        self.create_text(
            x + total_w + 12,
            number_y,
            text="m",
            fill=COLOUR_TEXT,
            font=FONT_7_BOLD,
            anchor="nw",
            tags=("scale_marker",),
        )


    def _draw_wall_labels(
        self,
        wall: str,
        wall_x: float,
        wall_y: float,
        wall_t_values: dict | None,
        wall_material_labels: dict | None,
        dose_labels: dict | None = None,
        wall_p_values: dict | None = None,
        role_labels: dict | None = None,
        fill: str | None = None,
        status: str | None = None,
    ) -> None:
        wall = str(wall).upper().strip()
        fill = fill or COLOUR_TEXT

        t_value = None
        if wall_t_values:
            t_value = wall_t_values.get(wall) or wall_t_values.get(f"{wall} wall")

        material = None
        if wall_material_labels:
            material = wall_material_labels.get(wall) or wall_material_labels.get(f"{wall} wall")

        heading = wall if not status else f"{wall} | {status}"
        lines = [heading]
        role_label = None
        if role_labels:
            role_label = role_labels.get(wall) or role_labels.get(f"{wall} wall")
        if role_label:
            lines.append(str(role_label))

        if t_value not in (None, ""):
            try:
                lines.append(f"T={float(t_value):g}")
            except Exception:
                lines.append(f"T={t_value}")

        p_value = None
        if wall_p_values:
            p_value = wall_p_values.get(wall) or wall_p_values.get(f"{wall} wall")

        if p_value not in (None, ""):
            try:
                lines.append(f"P={float(p_value):g} µSv/wk")
            except Exception:
                lines.append(f"P={p_value}")

        if material:
            lines.append(str(material))
        dose = None
        if dose_labels:
            dose = dose_labels.get(f"{wall} wall") or dose_labels.get(wall)

        self._append_dose_label_lines(lines, dose)

        OFFSET_NS = WALL_LABEL_OFFSET_NS
        OFFSET_EW = WALL_LABEL_OFFSET_EW

        if wall == "N":
            x, y, anchor = wall_x, wall_y - OFFSET_NS, "center"
        elif wall == "S":
            x, y, anchor = wall_x, wall_y + OFFSET_NS, "center"
        elif wall == "E":
            x, y, anchor = wall_x + OFFSET_EW, wall_y, "w"
        elif wall == "W":
            x, y, anchor = wall_x - OFFSET_EW, wall_y, "e"
        else:
            x, y, anchor = wall_x, wall_y, "center"

        LINE_SPACING = WALL_LABEL_LINE_SPACING
        NS_LABEL_GAP = 18

        if wall == "N":
            # Keep the entire N label block above the wall, with a fixed gap.
            start_y = wall_y - NS_LABEL_GAP - (LINE_SPACING * (len(lines) - 1))
        elif wall == "S":
            # Keep the entire S label block below the wall, with a fixed gap.
            start_y = wall_y + NS_LABEL_GAP
        else:
            # E/W labels remain vertically centred beside the wall.
            start_y = y - (LINE_SPACING * (len(lines) - 1) / 2)

        for i, line in enumerate(lines):
            font = FONT_7_BOLD if i == 0 else FONT_7

            self.create_text(
                x,
                start_y + i * LINE_SPACING,
                text=line,
                anchor=anchor,
                fill=fill,
                font=font,
                tags=("wall_label_group", f"{wall} wall"),
            )


    def _draw_wall_t_label(self, wall: str, x: float, y: float, wall_t_values: dict | None) -> None:
        """Legacy helper disabled. Wall labels are now drawn by _draw_wall_labels()."""
        return


    def _draw_wall_material_label(self, wall: str, x: float, y: float, wall_material_labels: dict | None) -> None:
        """Legacy helper disabled. Wall labels are now drawn by _draw_wall_labels()."""
        return


    def _default_one_m_label(self, source_text: str) -> str:
        text = str(source_text or "").lower()
        if "spect" in text or "nm" in text:
            return "NM dose @ 1 m"
        if "x-ray" in text or "xray" in text:
            return "Workload basis @ 1 m"
        return "ksec @ 1 m"


    def _draw_opening(self, opening: Opening, geom: RoomGeometry, map_point, scale: float, opening_index: int) -> None:

        centre = float(opening.offset_m)
        width = max(0.0, float(opening.width_m))

        max_len = geom.width_m if opening.wall in ("N", "S") else geom.length_m

        half_width = width / 2.0

        centre = max(half_width, min(centre, max_len - half_width))

        start = centre - half_width
        end = centre + half_width

        if opening.wall == "N":
            p0 = map_point(start, geom.length_m)
            p1 = map_point(end, geom.length_m)
        elif opening.wall == "S":
            p0 = map_point(start, 0)
            p1 = map_point(end, 0)
        elif opening.wall == "E":
            p0 = map_point(geom.width_m, start)
            p1 = map_point(geom.width_m, end)
        else:
            p0 = map_point(0, start)
            p1 = map_point(0, end)

        otype = "viewing_panel" if opening.opening_type in {"lead_glass", "viewing_panel", "vp", "pb_glass"} else "door"

        opening_id = self._opening_canvas_id(opening, opening_index)

        risk_map = getattr(geom, "barrier_risk_map", {}) or {}
        state = str(risk_map.get(opening_id, "fail")).lower()

        if state == "fail":
            colour = COLOUR_FAIL
        elif state == "review":
            colour = COLOUR_REVIEW_DARK
        elif state == "pass":
            colour = COLOUR_PASS
        elif state in {"not_inspected", "n_a"}:
            colour = COLOUR_TEXT_MUTED
        else:
            colour = COLOUR_FAIL

        label = opening_id

        #------------------------------------------
        # DRAW THE OPENING AS A FILLED RECTANGLE
        #------------------------------------------
        opening_thickness_px = OPENING_THICKNESS_PX
        half = opening_thickness_px / 2

        x_a, y_a = p0
        x_b, y_b = p1

        if opening.wall in ("N", "S"):
            self.create_rectangle(
                min(x_a, x_b),
                y_a - half,
                max(x_a, x_b),
                y_a + half,
                fill=colour,
                outline=colour,
                tags=("opening", opening_id),
            )
        else:
            self.create_rectangle(
                x_a - half,
                min(y_a, y_b),
                x_a + half,
                max(y_a, y_b),
                fill=colour,
                outline=colour,
                tags=("opening", opening_id),
            )

        mid_x = (p0[0] + p1[0]) / 2
        mid_y = (p0[1] + p1[1]) / 2

        material = str(getattr(opening, "material", "") or "").strip()
        pb = getattr(opening, "pb_equiv_mm", None)

        lines = [label]

        if material:
            lines.append(material)

        try:
            pb_val = float(pb)
            if pb_val > 0:
                lines.append(f"Pb eq {pb_val:g} mm")
        except Exception:
            pass

        dose_labels = getattr(geom, "barrier_dose_label_map", {}) or {}
        dose = dose_labels.get(opening_id)

        self._append_dose_label_lines(lines, dose)

        text = "\n".join(lines)

        TOP_BOTTOM_LABEL_OFFSET = 36
        SIDE_LABEL_OFFSET = 10

        if opening.wall == "N":
            candidates = [
                (mid_x, mid_y + TOP_BOTTOM_LABEL_OFFSET, "center"),
                (mid_x - 18, mid_y + TOP_BOTTOM_LABEL_OFFSET, "e"),
                (mid_x + 18, mid_y + TOP_BOTTOM_LABEL_OFFSET, "w"),
                (mid_x, mid_y + TOP_BOTTOM_LABEL_OFFSET + 12, "center"),
            ]

        elif opening.wall == "S":
            candidates = [
                (mid_x, mid_y - TOP_BOTTOM_LABEL_OFFSET, "center"),
                (mid_x - 18, mid_y - TOP_BOTTOM_LABEL_OFFSET, "e"),
                (mid_x + 18, mid_y - TOP_BOTTOM_LABEL_OFFSET, "w"),
                (mid_x, mid_y - TOP_BOTTOM_LABEL_OFFSET - 12, "center"),
            ]

        elif opening.wall == "E":
            candidates = [
                (mid_x - SIDE_LABEL_OFFSET, mid_y, "e"),
                (mid_x - SIDE_LABEL_OFFSET - 6, mid_y, "e"),
                (mid_x - SIDE_LABEL_OFFSET - 12, mid_y, "e"),
            ]

        elif opening.wall == "W":
            candidates = [
                (mid_x + SIDE_LABEL_OFFSET, mid_y, "w"),
                (mid_x + SIDE_LABEL_OFFSET + 6, mid_y, "w"),
                (mid_x + SIDE_LABEL_OFFSET + 12, mid_y, "w"),
            ]

        else:
            candidates = [(mid_x, mid_y, "center")]

        if opening.wall == "E":
            text_justify = "right"
        elif opening.wall == "W":
            text_justify = "left"
        else:
            text_justify = "center"
        # Draw the opening label
        self._create_safe_text(
            candidates,
            text,
            font=FONT_7_BOLD,
            fill=colour,
            tags=("opening_label",opening_id),
            avoid_tags=(
                "room_outline",
                "scanner_label",
                "opening_label",
                "room_title",
                "scale_marker",
            ),
            justify=text_justify,
        )


    def _draw_control_wall(self, wall: ControlWall, geom: RoomGeometry, map_point, scale: float) -> None:
        import math
        cx, cy = map_point(float(wall.center_x_m), float(wall.center_y_m))
        half = max(0.1, float(wall.length_m)) * scale / 2.0
        theta = math.radians(float(wall.orientation_deg))
        dx = math.cos(theta) * half
        dy = -math.sin(theta) * half
        x1, y1 = cx - dx, cy - dy
        x2, y2 = cx + dx, cy + dy

        risk_map = getattr(geom, "barrier_risk_map", {}) or {}
        dose_labels = getattr(geom, "barrier_dose_label_map", {}) or {}
        colour = self._risk_colour_for_barrier(risk_map, "Control wall")

        self.create_line(x1, y1, x2, y2, width=3, fill=colour, tags=("control_wall",))

        # Fig. 5.2 style operator barrier: 45-degree nibs at both ends.
        # Nibs are real persisted geometry (default 0.75 m), not decorative pixels.
        nib = max(0.0, float(getattr(wall, "nib_length_m", 0.75))) * scale
        ux, uy = math.cos(theta), -math.sin(theta)
        nx, ny = -uy, ux
        if nib > 0.0:
            c45, s45 = math.sqrt(0.5), math.sqrt(0.5)
            # Both 45-degree nibs project to the same side of the main wall,
            # giving the simple open-U plan symbol used for a control barrier.
            v1x, v1y = (-ux * c45 - nx * s45), (-uy * c45 - ny * s45)
            v2x, v2y = ( ux * c45 - nx * s45), ( uy * c45 - ny * s45)
            self.create_line(x1, y1, x1 + nib*v1x, y1 + nib*v1y, width=3, fill=colour, tags=("control_wall",))
            self.create_line(x2, y2, x2 + nib*v2x, y2 + nib*v2y, width=3, fill=colour, tags=("control_wall",))

        # Risk is communicated by colour; repeating PASS/REVIEW/FAIL in the
        # canvas text is redundant and makes the geometry labels noisy.
        lines = ["Control wall", "SECONDARY — control wall"]
        try:
            lines.append(f"T={float(getattr(wall, 'occupancy_factor', 1.0)):g}")
        except Exception:
            pass
        try:
            lines.append(f"P={float(getattr(wall, 'design_goal_uSv_per_week', 100.0)):g} µSv/wk")
        except Exception:
            pass
        material = str(getattr(wall, "material", "") or "").strip()
        try:
            thickness = float(getattr(wall, "thickness_mm", 0.0) or 0.0)
            if material and thickness > 0:
                lines.append(f"{material} {thickness:.2f} mm")
            elif material:
                lines.append(material)
        except Exception:
            if material:
                lines.append(material)
        self._append_dose_label_lines(lines, dose_labels.get("Control wall"))

        # XR-20A: keep the complete text block above the Control Wall rather
        # than allowing it to straddle the wall/nibs.
        nib_points = [(x1, y1), (x2, y2)]
        if nib > 0.0:
            nib_points.extend([(x1 + nib*v1x, y1 + nib*v1y), (x2 + nib*v2x, y2 + nib*v2y)])
        label_x = cx
        top_y = min(point[1] for point in nib_points)
        anchor = "center"
        line_spacing = WALL_LABEL_LINE_SPACING
        start_y = top_y - 12 - (line_spacing * (len(lines) - 1))
        for i, line in enumerate(lines):
            self.create_text(
                label_x, start_y + i * line_spacing, text=line, anchor=anchor,
                fill=colour, font=FONT_7_BOLD if i == 0 else FONT_7,
                tags=("control_wall_label",),
            )


    def _draw_gxr_table_beam_footprint(self, cx: float, cy: float,
                                      rotation_deg: int, scale: float) -> None:
        """Display-only South-facing beam boundaries, terminating at table receptor.

        The tube is 1.2 m north of table centre, matching the fixed GXR icon.
        The 40 cm receptor footprint and divergent rays are illustrative only.
        No rays extend beyond the table or enter shielding calculations.
        """
        half = 0.20 * scale
        tube_y = cy - 1.20 * scale
        receptor_y = cy + 0.07 * scale
        colour = "#A77A22"
        for edge_x in (cx - half, cx + half):
            self.create_line(cx, tube_y, edge_x, receptor_y,
                             fill=colour, width=2, dash=(3, 5),
                             tags=("gxr_table_beam_envelope",))
        # The field is visible at the receptor and is fully inside the table.
        self.create_rectangle(cx - half, cy - half, cx + half, cy + half,
                              outline=colour, width=2, dash=(3, 5),
                              tags=("gxr_table_beam_footprint",))

    def _draw_gxr_bucky_beam_envelope(self, geom: RoomGeometry, map_point) -> None:
        """Illustrative chest-bucky primary field, independent of the table source.

        Plan-view only: fixed nominal 2.5 m source-to-receptor distance and
        0.6 m footprint. Neither value enters the shielding calculation.
        """
        bucky = geom.wall_bucky
        wall = str(getattr(bucky, "wall", "N") or "N").upper()
        along = float(getattr(bucky, "offset_m", 1.0))
        if wall in ("N", "S"):
            along = max(0., min(geom.width_m, along))
            target = (along, geom.length_m if wall == "N" else 0.)
            normal = (0., -1. if wall == "N" else 1.)
            tangent = (1., 0.)
        else:
            along = max(0., min(geom.length_m, along))
            target = (geom.width_m if wall == "E" else 0., along)
            normal = (-1. if wall == "E" else 1., 0.)
            tangent = (0., 1.)
        distance = min(2.5, geom.length_m if wall in ("N", "S") else geom.width_m)
        source = (target[0] + distance * normal[0], target[1] + distance * normal[1])
        half = 0.3
        colour = "#A77A22"
        for sign in (-1, 1):
            edge = (target[0] + sign * half * tangent[0], target[1] + sign * half * tangent[1])
            self.create_line(*map_point(*source), *map_point(*edge), fill=colour,
                             width=2, dash=(3, 5), tags=("gxr_beam_envelope",))
        self.create_line(*map_point(*source), *map_point(*target), fill=colour,
                         width=1, dash=(2, 7), tags=("gxr_beam_axis",))

    def _draw_wall_bucky(self, bucky: WallBucky, geom: RoomGeometry, map_point, scale: float) -> None:
        offset = max(0.0, float(getattr(bucky, "offset_m", 1.0)))
        wall = getattr(bucky, "wall", "N")
        max_len = geom.length_m if wall in ("N", "S") else geom.width_m
        offset = min(offset, max_len)
        # Anchor the bucky assembly on the actual wall face. The symbol helper
        # places the small rear plate touching the wall and the tall bucky on
        # the room side of it.
        if wall == "N":
            x, y = map_point(offset, geom.length_m)
        elif wall == "S":
            x, y = map_point(offset, 0)
        elif wall == "E":
            x, y = map_point(geom.width_m, offset)
        else:
            x, y = map_point(0, offset)
        shield = getattr(geom, "bucky_shield", None)
        if shield is not None:
            self._draw_bucky_shield(shield, geom, map_point, scale)
        draw_chest_bucky_tube_combo(self, x, y, wall=wall, scale=scale, distance_m=2.5)

    def _draw_bucky_shield(self, shield: BuckyShield, geom: RoomGeometry, map_point, scale: float) -> None:
        """Draw the fixed 1.2 m / 2.2 mm Pb Chest Bucky shield just outside the room."""
        wall = str(getattr(shield, "wall", "N") or "N").upper()
        offset = max(0.0, float(getattr(shield, "offset_m", 1.0)))
        width = 1.2  # qualified XR-19A geometry default; physics credit is not yet enabled
        half = width * scale / 2.0
        outside_px = 7.0
        if wall == "N":
            cx, cy = map_point(offset, geom.length_m)
            x0, y0, x1, y1 = cx-half, cy-outside_px, cx+half, cy-outside_px
        elif wall == "S":
            cx, cy = map_point(offset, 0.0)
            x0, y0, x1, y1 = cx-half, cy+outside_px, cx+half, cy+outside_px
        elif wall == "E":
            cx, cy = map_point(geom.width_m, offset)
            x0, y0, x1, y1 = cx+outside_px, cy-half, cx+outside_px, cy+half
        else:
            cx, cy = map_point(0.0, offset)
            x0, y0, x1, y1 = cx-outside_px, cy-half, cx-outside_px, cy+half
        risk_map = getattr(geom, "barrier_risk_map", {}) or {}
        dose_labels = getattr(geom, "barrier_dose_label_map", {}) or {}
        colour = self._risk_colour_for_barrier(risk_map, "Bucky shield")
        self.create_line(x0, y0, x1, y1, width=5, fill=colour, tags=("bucky_shield",))

        # XR-20A: the 1.2 m region behind the Chest Bucky is a separate
        # sub-barrier physics check. Put its own text block immediately outside
        # the shield; the remainder of the parent wall keeps its own result.
        # XR-20B: T and P belong to the occupied area beyond the parent wall,
        # so the finite Bucky Shield sub-barrier inherits them rather than
        # defining independent design inputs.  The canonical dose label map
        # carries the inherited values from the parent chest-bucky wall.
        lines = ["Bucky shield", "PRIMARY — shielded sub-barrier", "Width 1.20 m", "Pb 2.20 mm"]
        self._append_dose_label_lines(lines, dose_labels.get("Bucky shield"))
        spacing = WALL_LABEL_LINE_SPACING
        if wall == "N":
            tx, ty, anchor = (x0+x1)/2, y0-12-(spacing*(len(lines)-1)), "center"
        elif wall == "S":
            tx, ty, anchor = (x0+x1)/2, y0+12, "center"
        elif wall == "E":
            tx, ty, anchor = x0+12, (y0+y1)/2-(spacing*(len(lines)-1)/2), "w"
        else:
            tx, ty, anchor = x0-12, (y0+y1)/2-(spacing*(len(lines)-1)/2), "e"
        for i, line in enumerate(lines):
            self.create_text(tx, ty+i*spacing, text=line, anchor=anchor, fill=colour,
                             font=FONT_7_BOLD if i == 0 else FONT_7, tags=("bucky_shield_label",))


    def _text_bbox_overlaps(self, bbox1, bbox2, pad: int = 4) -> bool:
        if not bbox1 or not bbox2:
            return False

        x0, y0, x1, y1 = bbox1
        a0, b0, a1, b1 = bbox2

        return not (
            x1 + pad < a0 or
            x0 - pad > a1 or
            y1 + pad < b0 or
            y0 - pad > b1
        )


    def _create_safe_text(
        self,
        candidate_positions: list[tuple[float, float, str]],
        text: str,
        *,
        font=FONT_8_BOLD,
        fill=COLOUR_TEXT,
        tags=("safe_label",),
        avoid_tags=("room_outline", "scanner_label", "opening_label", "room_title", "scale_marker"),
        justify="center",
    ):
        avoid_boxes = []

        for tag in avoid_tags:
            for item in self.find_withtag(tag):
                bbox = self.bbox(item)
                if bbox:
                    avoid_boxes.append(bbox)

        chosen = candidate_positions[-1]

        for x, y, anchor in candidate_positions:
            item = self.create_text(
                x,
                y,
                text=text,
                anchor=anchor,
                justify=justify,
                font=font,
                fill=fill,
                tags=tags,
            )

            bbox = self.bbox(item)

            if not any(self._text_bbox_overlaps(bbox, other, pad=6) for other in avoid_boxes):
                chosen = (x, y, anchor)
                return item

            self.delete(item)

        x, y, anchor = chosen
        return self.create_text(
            x,
            y,
            text=text,
            anchor=anchor,
            justify=justify,
            font=font,
            fill=fill,
            tags=tags,
        )


    def _opening_canvas_id(self, opening, opening_index: int) -> str:
        raw_type = str(getattr(opening, "opening_type", "") or "").strip().lower()
        is_vp = raw_type in {"viewing_panel", "lead_glass", "vp", "pb_glass"}

        explicit = str(getattr(opening, "id", "") or "").strip()
        if explicit:
            return explicit

        prefix = "VP" if is_vp else "D"
        return f"{prefix}{opening_index}"
    

    def _draw_floor_ceiling_labels(
        self,
        field_x0: float,
        field_y0: float,
        field_w_px: float,
        scale: float,
        wall_t_values: dict | None,
        wall_material_labels: dict | None,
        dose_labels: dict | None = None,
        wall_p_values: dict | None = None,
        wall_distance_values: dict | None = None,
        risk_map: dict | None = None,
        role_labels: dict | None = None,
        show_status_text: bool = True,
    ) -> None:
        """
        Draw Floor and Ceiling barrier labels in the upper left/right corners
        of the fixed design grid.

        This is a canvas-only visual label. The actual Floor/Ceiling barrier
        model entries will be added separately.
        """

        ceiling_x = field_x0 + 0.75 * scale
        floor_x = field_x0 + field_w_px - 0.75 * scale
        label_y = field_y0 + 0.55 * scale

        self._draw_planar_barrier_label(
            label="Ceiling",
            key_options=("Ceiling",),
            x=ceiling_x,
            y=label_y,
            anchor="w",
            wall_t_values=wall_t_values,
            wall_material_labels=wall_material_labels,
            dose_labels=dose_labels,
            wall_p_values=wall_p_values,
            wall_distance_values=wall_distance_values,
            role_labels=role_labels,
            fill=self._risk_colour_for_barrier(risk_map, "Ceiling"),
            status=self._risk_status_for_barrier(risk_map, "Ceiling") if show_status_text else "",
        )

        self._draw_planar_barrier_label(
            label="Floor",
            key_options=("Floor",),
            x=floor_x,
            y=label_y,
            anchor="e",
            wall_t_values=wall_t_values,
            wall_material_labels=wall_material_labels,
            dose_labels=dose_labels,
            wall_p_values=wall_p_values,
            wall_distance_values=wall_distance_values,
            role_labels=role_labels,
            fill=self._risk_colour_for_barrier(risk_map, "Floor"),
            status=self._risk_status_for_barrier(risk_map, "Floor") if show_status_text else "",
        )


    def _draw_planar_barrier_label(
        self,
        label: str,
        key_options: tuple[str, ...],
        x: float,
        y: float,
        anchor: str,
        wall_t_values: dict | None,
        wall_material_labels: dict | None,
        dose_labels: dict | None = None,
        wall_p_values: dict | None = None,
        wall_distance_values: dict | None = None,
        role_labels: dict | None = None,
        fill: str | None = None,
        status: str | None = None,
    ) -> None:
        heading = label
        if status:
            heading = f"{label} | {status}"
        lines = [heading]
        fill = fill or COLOUR_TEXT

        def lookup(mapping: dict | None):
            if not mapping:
                return None

            def norm(value: object) -> str:
                return (
                    str(value or "")
                    .strip()
                    .lower()
                    .replace("_", " ")
                    .replace("-", " ")
                )

            wanted = set()

            for key in key_options:
                base = norm(key)

                wanted.add(base)
                wanted.add(f"{base} barrier")
                wanted.add(f"{base} wall")
                wanted.add(f"{base} slab")

            for raw_key, value in mapping.items():
                if norm(raw_key) in wanted:
                    return value

            return None

        t_value = lookup(wall_t_values)
        p_value = lookup(wall_p_values)
        distance_value = lookup(wall_distance_values)
        material = lookup(wall_material_labels)
        dose = lookup(dose_labels)
        role_label = lookup(role_labels)
        if role_label:
            lines.append(str(role_label))

        if distance_value not in (None, ""):
            try:
                lines.append(f"Distance={float(distance_value):.2f} m")
            except Exception:
                lines.append(f"Distance={distance_value}")

        if t_value not in (None, ""):
            try:
                lines.append(f"T={float(t_value):g}")
            except Exception:
                lines.append(f"T={t_value}")

        if p_value not in (None, ""):
            try:
                lines.append(f"P={float(p_value):g} µSv/wk")
            except Exception:
                lines.append(f"P={p_value}")

        if material:
            lines.append(str(material))

        self._append_dose_label_lines(lines, dose)

        line_spacing = WALL_LABEL_LINE_SPACING
        start_y = y

        for i, line in enumerate(lines):
            font = FONT_7_BOLD if i == 0 else FONT_7

            self.create_text(
                x,
                start_y + i * line_spacing,
                text=line,
                anchor=anchor,
                fill=fill,
                font=font,
                tags=("floor_ceiling_label", label),
            )


    def _risk_status_for_barrier(self, risk_map: dict | None, barrier_name: str) -> str:
        """Return a visible PASS/REVIEW/FAIL label when a live risk state exists."""
        if not risk_map:
            return ""

        state = str(risk_map.get(barrier_name, "") or "").strip().lower()
        if state == "fail":
            return "FAIL"
        if state == "review":
            return "REVIEW"
        if state == "pass":
            return "PASS"
        if state == "not_inspected":
            return "NOT INSPECTED"
        if state == "n_a":
            return "N/A"
        return ""


    def _risk_colour_for_barrier(self, risk_map: dict | None, barrier_name: str) -> str:
        """
        Return display colour for a barrier label based on risk state.

        Expected risk states:
        - pass   -> green
        - review -> amber
        - fail   -> red

        Falls back to black text if no risk state exists.
        """

        if not risk_map:
            return COLOUR_TEXT

        state = str(risk_map.get(barrier_name, "") or "").strip().lower()

        if state == "fail":
            return COLOUR_FAIL

        if state == "review":
            return COLOUR_REVIEW_DARK

        if state == "pass":
            return COLOUR_PASS

        if state in {"not_inspected", "n_a"}:
            return COLOUR_TEXT_MUTED

        return COLOUR_TEXT
    

    def _append_dose_label_lines(self, lines: list[str], dose) -> None:
        """
        Append transmitted/unshielded dose label lines with visual separation
        from the construction/material line above.
        """
        if not dose:
            return

        dose_lines = [
            str(line).strip()
            for line in str(dose).splitlines()
            if str(line).strip()
        ]

        if not dose_lines:
            return

        if lines:
            lines.append("")  # visual spacer between Pb/material and Tx

        lines.extend(dose_lines)