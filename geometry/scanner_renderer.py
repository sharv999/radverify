from __future__ import annotations

import math

from config.geometry_constants import *
from config.ui_constants import *
from tabs.results_barrier_maps import get_barrier_dose_label_map

class ScannerRendererMixin:

    def _draw_equipment_symbol(self, g, room_bbox, layout_rendering):
        x0, y0, x1, y1 = room_bbox
        room_w_px = x1 - x0
        room_h_px = y1 - y0

        if g.length_m <= 0 or g.width_m <= 0:
            return

        iso_x = x0 + (g.source.x_m / g.width_m) * room_w_px
        iso_y = y1 - (g.source.y_m / g.length_m) * room_h_px

        px_per_m = min(room_w_px / g.width_m, room_h_px / g.length_m)

        rotation = int(self.scanner_rotation_var.get() or 0) % 360

        gantry_width_px = float(layout_rendering.get("equipment_width_m", 0.0) or 0.0) * px_per_m
        gantry_depth_px = float(layout_rendering.get("equipment_depth_m", 0.0) or 0.0) * px_per_m
        table_width_px = float(layout_rendering.get("table_width_m", 0.0) or 0.0) * px_per_m
        table_length_px = float(layout_rendering.get("table_length_m", 0.0) or 0.0) * px_per_m
        if gantry_width_px <= 0 or gantry_depth_px <= 0:
            return

        corner_r = 0.2 * px_per_m
        projection_px = float(layout_rendering.get("projection_length_m", 0.5) or 0.5) * px_per_m

        def rot(dx, dy):
            if rotation == 0:
                return iso_x + dx, iso_y + dy
            if rotation == 90:
                return iso_x - dy, iso_y + dx
            if rotation == 180:
                return iso_x - dx, iso_y - dy
            if rotation == 270:
                return iso_x + dy, iso_y - dx
            return iso_x + dx, iso_y + dy

        def rect_from_local(cx, cy, w, h):
            # Only 90-degree rotations, so local rectangle stays axis-aligned after transform
            pts = [
                rot(cx - w / 2, cy - h / 2),
                rot(cx + w / 2, cy - h / 2),
                rot(cx + w / 2, cy + h / 2),
                rot(cx - w / 2, cy + h / 2),
            ]
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            return min(xs), min(ys), max(xs), max(ys)

        # Gantry centred on isocentre
        gx0, gy0, gx1, gy1 = rect_from_local(
            0,
            0,
            gantry_width_px,
            gantry_depth_px,
        )

        self._draw_rounded_rect(
            gx0, gy0, gx1, gy1,
            r=corner_r,
            outline=COLOUR_SCANNER,
            width=2,
        )

        # Table extends local south from bottom of gantry
        table_cy = gantry_depth_px / 2 + table_length_px / 2
        tx0, ty0, tx1, ty1 = rect_from_local(
            0,
            table_cy,
            table_width_px,
            table_length_px,
        )

        self.canvas.create_rectangle(
            tx0, ty0, tx1, ty1,
            outline=COLOUR_SCANNER,
            width=2,
        )

        # Scanner model label aligned with table
        scanner_label = self.source_option_var.get().strip()

        try:
                room = self.get_selected_room()

                tx_dose = None

                if room:
                    dose_map = get_barrier_dose_label_map(self.app, room.name)

                    # use selected barrier wall
                    selected_wall = str(self.barrier_wall_var.get()).strip().upper()
                    barrier_name = f"{selected_wall} wall"

                    tx_dose = dose_map.get(barrier_name)

                if tx_dose:
                    line3 = tx_dose

        except Exception:
            pass

        # Plugin-owned label cleanup keeps the renderer modality-neutral.
        for phrase in list(layout_rendering.get("label_cleanup_phrases", []) or []):
            scanner_label = scanner_label.replace(str(phrase), "").strip()

        if scanner_label:
            label = scanner_label
            label = label.replace(" / ", "\n/ ")
            label = label.replace("Apex Elite", "\nApex Elite")

            x = (tx0 + tx1) / 2
            y = (ty0 + ty1) / 2

            # 90° CCW relative to the table/scanner
            label_angle = (rotation + 90) % 360

            self.canvas.create_text(
                x,
                y,
                text=label,
                anchor="center",
                angle=label_angle,
                fill=COLOUR_TEXT,
                font=FONT_8,
                justify="center",
            )

        # Projected isocentre lines
        # Local horizontal line through gantry
        hx0, hy0 = rot(-gantry_width_px / 2 - projection_px, 0)
        hx1, hy1 = rot(gantry_width_px / 2 + projection_px, 0)
        self.canvas.create_line(
            hx0, hy0, hx1, hy1,
            fill=COLOUR_SCANNER,
            width=1,
            dash=(8, 5),
        )

         # Local vertical line through gantry/table
        vx0, vy0 = rot(0, -gantry_depth_px / 2 - projection_px)
        vx1, vy1 = rot(0, gantry_depth_px / 2 + table_length_px + projection_px)
        self.canvas.create_line(
            vx0, vy0, vx1, vy1,
            fill=COLOUR_SCANNER,
            width=1,
            dash=(8, 5),
        )


    def _draw_rounded_rect(self, x0, y0, x1, y1, r, **kwargs):
        """
        Draw a rounded rectangle using lines + arcs.
        r = corner radius in pixels
        """

        c = self.canvas

        # --- FIX: convert outline → fill for line drawing ---
        line_kwargs = dict(kwargs)
        if "outline" in line_kwargs:
            line_kwargs["fill"] = line_kwargs.pop("outline")

        # Clamp radius
        r = min(r, (x1 - x0) / 2, (y1 - y0) / 2)

        # Straight edges (LINES → need fill)
        c.create_line(x0 + r, y0, x1 - r, y0, **line_kwargs)  # top
        c.create_line(x0 + r, y1, x1 - r, y1, **line_kwargs)  # bottom
        c.create_line(x0, y0 + r, x0, y1 - r, **line_kwargs)  # left
        c.create_line(x1, y0 + r, x1, y1 - r, **line_kwargs)  # right

        # Corners (ARCS → can still use outline)
        c.create_arc(x0, y0, x0 + 2*r, y0 + 2*r,
            start=90, extent=90, style="arc", **kwargs)
        c.create_arc(x1 - 2*r, y0, x1, y0 + 2*r,
            start=0, extent=90, style="arc", **kwargs)
        c.create_arc(x1 - 2*r, y1 - 2*r, x1, y1,
            start=270, extent=90, style="arc", **kwargs)
        c.create_arc(x0, y1 - 2*r, x0 + 2*r, y1,
            start=180, extent=90, style="arc", **kwargs)
