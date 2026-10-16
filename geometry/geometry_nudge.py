from __future__ import annotations

from config.geometry_constants import *


class GeometryNudgeMixin:

    def nudge_source_position(self, axis: str, delta_m: float):
        """Move the CT/source position and force the same model update path as manual editing."""
        if getattr(self, "_loading", False):
            return

        axis_key = str(axis or "").strip().lower()
        if axis_key not in {"x", "y"}:
            return

        var = self.source_x_var if axis_key == "x" else self.source_y_var

        try:
            current = float(var.get())
            step = float(delta_m)
        except Exception:
            return

        var.set(round(current + step, 3))

        # Force commit to room.geometry.source.x_m/y_m.
        self.update_model_from_fields(show_errors=False)

        # CT-07: source-position nudges must trigger the same downstream
        # geometry -> barrier-distance -> results sync as room-dimension nudges.
        # update_model_from_fields() updates the local RoomGeometry, but callers
        # can still leave Results on stale N/E/S/W distances unless the app-level
        # geometry sync callback is explicitly fired here.
        if callable(getattr(self, "on_change", None)):
            self.on_change()

        # Force immediate redraw rather than relying only on trace/after_idle behaviour.
        if hasattr(self, "draw_room_with_risk"):
            self.draw_room_with_risk()
        elif hasattr(self, "request_redraw"):
            self.request_redraw()


    def nudge_room_dimension(self, dim: str, delta_m: float):
        """Nudge room length/width/height and immediately refresh model + drawing."""
        if getattr(self, "_loading", False):
            return

        try:
            dim_key = str(dim or "").strip().lower()
            step = float(delta_m)

            if dim_key == "length":
                current = float(self.length_var.get())
                new_val = max(MIN_ROOM_DIMENSION_M, current + step)
                self.length_var.set(round(new_val, 3))

            elif dim_key == "width":
                current = float(self.width_var.get())
                new_val = max(MIN_ROOM_DIMENSION_M, current + step)
                self.width_var.set(round(new_val, 3))

            elif dim_key == "height":
                current = float(self.height_var.get())
                new_val = max(MIN_ROOM_DIMENSION_M, current + step)
                self.height_var.set(round(new_val, 3))

            else:
                return

            # Commit the field change into room.geometry.
            self.update_model_from_fields(show_errors=False)

            # Trigger the same downstream sync path used by normal geometry edits.
            if callable(getattr(self, "on_change", None)):
                self.on_change()

            # Force immediate visual feedback rather than relying only on trace/after_idle.
            if hasattr(self, "draw_room_with_risk"):
                self.draw_room_with_risk()
            elif hasattr(self, "request_redraw"):
                self.request_redraw()

        except Exception:
            pass
    

    def nudge_opening_offset(self, delta_m: float):
        g, opening, index = self.get_selected_opening()
        if opening is None:
            return

        try:
            current = float(getattr(opening, "offset_m", 0.0) or 0.0)
        except Exception:
            current = 0.0

        new_value = current + float(delta_m)

        opening.offset_m = new_value
        self.opening_offset_var.set(f"{new_value:.2f}")

        self.refresh_after_opening_edit()


    def rotate_scanner_cw(self):
        current = int(self.scanner_rotation_var.get() or 0)
        new_rotation = (current + SCANNER_ROTATION_STEP_DEG) % 360
        self.scanner_rotation_var.set(new_rotation)

        if self.geometry and getattr(self.geometry, "source", None):
            self.geometry.source.rotation_deg = new_rotation

        # Do not call update_model_from_fields() here,
        # because it clamps the CT footprint and can move the isocentre.
        self.request_redraw()

        if callable(self.on_change):
            self.on_change()


    def _clamp_ct_scanner_inside_room(self) -> None:
        if not self.geometry:
            return

        g = self.geometry
        source = getattr(g, "source", None)

        if source is None:
            return

        rotation = int(self.scanner_rotation_var.get() or 0) % 360

        # Scanner footprint in LOCAL scanner coordinates
        # Scanner centred at gantry isocentre
        local_left = max(CT_GANTRY_WIDTH_M / 2, CT_TABLE_WIDTH_M / 2)
        local_right = local_left

        local_up = CT_GANTRY_DEPTH_M / 2
        local_down = CT_GANTRY_DEPTH_M / 2 + CT_TABLE_LENGTH_M

        if rotation == 0:
            west, east, north, south = (
                local_left,
                local_right,
                local_up,
                local_down,
            )

        elif rotation == 90:
            west, east, north, south = (
                local_down,
                local_up,
                local_left,
                local_right,
            )

        elif rotation == 180:
            west, east, north, south = (
                local_right,
                local_left,
                local_down,
                local_up,
            )

        else:  # 270
            west, east, north, south = (
                local_up,
                local_down,
                local_right,
                local_left,
            )

        source.x_m = max(
            west,
            min(float(source.x_m), float(g.width_m) - east)
        )

        source.y_m = max(
            south,
            min(float(source.y_m), float(g.length_m) - north)
        )


