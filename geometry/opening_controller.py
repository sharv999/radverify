from __future__ import annotations

from typing import Optional

from geometry.geometry_model import Opening
from config.geometry_constants import *
from config.material_constants import *

class OpeningControllerMixin:

    def _snapshot_parent_wall_design_fields(self):
        """Capture structural-wall design fields before an opening edit.

        Openings are sub-barriers and have no authority over their parent
        wall construction, occupancy or design goal.
        """
        room = self.get_selected_room()
        snapshot = {}
        if room is None:
            return snapshot
        for barrier in getattr(room, "barriers", []) or []:
            name = str(getattr(barrier, "name", "") or "").strip()
            if name.upper() in {"N WALL", "E WALL", "S WALL", "W WALL"}:
                snapshot[name.lower()] = (
                    getattr(barrier, "material", "Pb"),
                    float(getattr(barrier, "thickness_mm", 0.88) or 0.88),
                    float(getattr(barrier, "occupancy_factor", 1.0) or 0.0),
                    float(getattr(barrier, "design_goal_uSv_per_week", 10.0) or 0.0),
                    getattr(barrier, "material_legacy", None),
                )
        return snapshot

    def _restore_parent_wall_design_fields(self, snapshot):
        room = self.get_selected_room()
        if room is None or not snapshot:
            return
        for barrier in getattr(room, "barriers", []) or []:
            key = str(getattr(barrier, "name", "") or "").strip().lower()
            values = snapshot.get(key)
            if values is None:
                continue
            material, thickness, occupancy, design_goal, material_legacy = values
            barrier.material = material
            barrier.thickness_mm = thickness
            barrier.occupancy_factor = occupancy
            barrier.design_goal_uSv_per_week = design_goal
            if material_legacy is not None:
                barrier.material_legacy = material_legacy

    def add_opening(self):
        wall_design = self._snapshot_parent_wall_design_fields()
        room = self.get_selected_room()
        if not room:
            return

        self.update_model_from_fields(show_errors=False)
        g = self.ensure_room_geometry(room)

        # ✅ define FIRST
        otype_ui = self.opening_type_var.get().strip().lower()
        otype = "door" if otype_ui == "door" else "viewing_panel"

        material = (
            self.opening_material_var.get().strip()
            or self._default_opening_material(otype)
        )

        try:
            pb_val = float(self.opening_pb_var.get())
        except Exception:
            pb_val = 0.0

        opening = Opening(
            wall=self.opening_wall_var.get(),
            opening_type=otype,
            offset_m=float(self.opening_offset_var.get()),
            width_m=float(self.opening_width_var.get()),
            pb_equiv_mm=pb_val,
            material=material,
            sill_height_above_ffl_m=0.0 if otype == "door" else 0.9,
            head_height_above_ffl_m=2.1 if otype == "door" else 1.8,
            kvp_basis=120.0,
        )

        g.openings.append(opening)
        self._clamp_opening_to_wall(opening)

        self.refresh_opening_selector()
        self.selected_opening_var.set(self.opening_display_id(opening, len(g.openings)))
        self.load_selected_opening_into_fields()    

        # Restore parent-wall design before redraw/notification.
        self._restore_parent_wall_design_fields(wall_design)

        # Openings are sub-barriers and have no authority over parent walls.
        self.request_redraw()

        if callable(self.on_change):
            self.on_change()


    def clear_openings(self):
        wall_design = self._snapshot_parent_wall_design_fields()
        room = self.get_selected_room()
        if not room:
            return

        g = self.ensure_room_geometry(room)
        g.openings.clear()
        self.refresh_opening_selector()

        self._restore_parent_wall_design_fields(wall_design)
        self.request_redraw()

        if callable(self.on_change):
            self.on_change()


    def get_selected_opening(self):
        room = self.get_selected_room()
        if not room:
            return None, None, None

        g = self.ensure_room_geometry(room)
        openings = getattr(g, "openings", []) or []

        selected = self.selected_opening_var.get().strip()
        if not selected or not openings:
            return g, None, None

        for i, opening in enumerate(openings, start=1):
            if self.opening_display_id(opening, i) == selected:
                return g, opening, i

        return g, None, None


    def refresh_opening_selector(self):
        room = self.get_selected_room()
        if not room or not hasattr(self, "opening_select_combo"):
            return

        g = self.ensure_room_geometry(room)
        openings = getattr(g, "openings", []) or []

        values = [
            self.opening_display_id(opening, i)
            for i, opening in enumerate(openings, start=1)
        ]

        self.opening_select_combo["values"] = values

        current = self.selected_opening_var.get()
        if values and current not in values:
            self.selected_opening_var.set(values[-1])
        elif not values:
            self.selected_opening_var.set("")


    def load_selected_opening_into_fields(self, event=None):
        if self._opening_loading:
            return

        g, opening, index = self.get_selected_opening()
        if opening is None:
            return

        self._opening_loading = True

        try:
            self.opening_wall_var.set(str(getattr(opening, "wall", "N")))

            otype = str(getattr(opening, "opening_type", "door")).lower()

            self.opening_type_var.set(
                "Viewing Panel"
                if otype in {"viewing_panel", "lead_glass", "vp", "pb_glass"}
                else "Door"
            )

            self.opening_material_var.set(
                str(
                    getattr(opening, "material", "")
                    or ("Pb glass" if otype == "viewing_panel" else "Pb")
                )
            )

            self.opening_offset_var.set(
                f"{float(getattr(opening, 'offset_m', 0.0) or 0.0):.2f}"
            )

            self.opening_width_var.set(
                f"{float(getattr(opening, 'width_m', 0.9) or 0.9):.2f}"
            )

            self.opening_pb_var.set(
                f"{float(getattr(opening, 'pb_equiv_mm', 0.88) or 0.88):.2f}"
            )

        finally:
            self._opening_loading = False


    def update_selected_opening_from_fields(self, *_):
        wall_design = self._snapshot_parent_wall_design_fields()
        g, opening, index = self.get_selected_opening()
        if opening is None:
            return

        otype_ui = str(self.opening_type_var.get()).strip().lower()

        if otype_ui in {"viewing panel", "viewing_panel", "vp", "lead_glass"}:
            opening.opening_type = "viewing_panel"
        else:
            opening.opening_type = "door"

        opening.material = (
            self.opening_material_var.get().strip()
            or self._default_opening_material(opening.opening_type)
        )

        # Wall
        opening.wall = self.opening_wall_var.get()

        # Geometry
        try:
            opening.offset_m = float(self.opening_offset_var.get())
        except Exception:
            pass

        try:
            opening.width_m = float(self.opening_width_var.get())
        except Exception:
            pass

        # Thickness
        try:
            opening.pb_equiv_mm = float(self.opening_pb_var.get())
        except Exception:
            pass

        self._clamp_opening_to_wall(opening)
        self.opening_offset_var.set(f"{opening.offset_m:.2f}")
        self.opening_width_var.set(f"{opening.width_m:.2f}")
        self._restore_parent_wall_design_fields(wall_design)
        self.refresh_after_opening_edit()


    def update_current_opening_thickness(self, *_):
        wall_design = self._snapshot_parent_wall_design_fields()
        if self._opening_loading:
            return
        
        room = self.get_selected_room()
        if not room:
            return

        g = self.ensure_room_geometry(room)
        if not getattr(g, "openings", None):
            return

        try:
            pb_val = float(self.opening_pb_var.get())
        except Exception:
            return

        # For now: update most recently added opening
        g, opening, index = self.get_selected_opening()
        if opening is None:
            return

        opening.pb_equiv_mm = pb_val

        # Type
        otype_ui = str(self.opening_type_var.get()).strip().lower()

        if otype_ui in {"viewing panel", "viewing_panel", "vp", "lead_glass"}:
            opening.opening_type = "viewing_panel"
        else:
            opening.opening_type = "door"

        opening.material = (
            self.opening_material_var.get().strip()
            or self._default_opening_material(opening.opening_type)
        )

        self._restore_parent_wall_design_fields(wall_design)
        self.refresh_after_opening_edit()


    def refresh_opening_material_combo(self):
        otype = str(self.opening_type_var.get()).strip().lower()

        current = self.opening_material_var.get().strip()

        if otype in {"viewing panel", "viewing_panel", "vp", "lead_glass"}:
            values = ["Pb glass"]
        else:
            values = self._opening_material_values("door")

        self.opening_material_combo["values"] = values

        if current not in values:
            new_value = values[0]

            if self.opening_material_var.get() != new_value:
                self.opening_material_var.set(new_value)


    def _clamp_opening_to_wall(self, opening) -> None:
        """
        Keep opening fully within its parent wall.

        Source of truth:
        - opening.offset_m = centre distance along wall
        - opening.width_m = physical opening width
        """

        if not self.geometry or opening is None:
            return

        g = self.geometry

        wall = str(getattr(opening, "wall", "") or "").strip().upper()

        if wall in {"N", "S"}:
            wall_length = float(g.width_m)
        elif wall in {"E", "W"}:
            wall_length = float(g.length_m)
        else:
            return

        try:
            width = float(getattr(opening, "width_m", 0.0) or 0.0)
        except Exception:
            width = DEFAULT_DOOR_WIDTH_M

        width = max(MIN_OPENING_WIDTH_M, min(width, wall_length))

        half_width = width / 2.0

        try:
            offset = float(getattr(opening, "offset_m", half_width) or half_width)
        except Exception:
            offset = half_width

        offset = max(half_width, min(offset, wall_length - half_width))

        opening.width_m = width
        opening.offset_m = offset

