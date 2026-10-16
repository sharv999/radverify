from __future__ import annotations

from config.geometry_constants import *
from engine.shielding_engine import default_barriers


class BarrierSyncMixin:

    def _wall_t_values_for_canvas(self, room=None) -> dict:
        """Return occupancy factors for wall/floor/ceiling canvas annotation."""
        room = room or self.get_selected_room()
        out = {
            "N": None,
            "E": None,
            "S": None,
            "W": None,
            "Floor": None,
            "Ceiling": None,
        }

        if not room:
            return out

        name_to_key = {
            "n wall": "N",
            "north wall": "N",
            "e wall": "E",
            "east wall": "E",
            "s wall": "S",
            "south wall": "S",
            "w wall": "W",
            "west wall": "W",
            "floor": "Floor",
            "floor barrier": "Floor",
            "floor slab": "Floor",
            "ceiling": "Ceiling",
            "ceiling barrier": "Ceiling",
            "ceiling slab": "Ceiling",
        }

        role_to_key = {
            "floor": "Floor",
            "ceiling": "Ceiling",
            "secondary_wall": None,
        }

        for b in getattr(room, "barriers", []) or []:
            raw_name = str(getattr(b, "name", "") or "").strip().lower()
            raw_role = str(getattr(b, "barrier_role", "") or "").strip().lower()

            key = name_to_key.get(raw_name)

            if not key:
                key = role_to_key.get(raw_role)

            if not key:
                continue

            try:
                out[key] = float(getattr(b, "occupancy_factor", 0.2) or 0.2)
            except Exception:
                out[key] = 0.2

        return out
    

    def _barrier_name_from_wall(self, wall: str) -> str:
        value = str(wall or "").strip()

        if value.lower() == "floor":
            return "Floor"

        if value.lower() == "ceiling":
            return "Ceiling"

        return f"{value.upper()} wall"
    

    def load_selected_barrier_fields(self):
        if getattr(self, "_loading", False):
            return

        room = self.get_selected_room()
        if not room:
            self._refresh_barrier_distance_entry_state()
            return

        target = self._barrier_name_from_wall(self.barrier_wall_var.get())

        for b in getattr(room, "barriers", []) or []:
            if str(getattr(b, "name", "")).strip().lower() == target.lower():
                self._loading = True
                try:
                    self.barrier_material_var.set(
                        str(getattr(b, "material", "Pb") or "Pb")
                    )

                    self.barrier_thickness_var.set(
                        f"{float(getattr(b, 'thickness_mm', 0.88) or 0.88):.2f}"
                    )

                    self.barrier_t_var.set(
                        self._normalise_t_value(
                            getattr(b, "occupancy_factor", 0.2)
                        )
                    )

                    try:
                        p_val = float(
                            getattr(b, "design_goal_uSv_per_week", 10.0) or 10.0
                        )
                    except Exception:
                        p_val = 10.0

                    self.p_var.set(f"{p_val:g} µSv/wk")

                    try:
                        d_val = float(getattr(b, "distance_m", 0.0) or 0.0)
                        self.barrier_distance_var.set(f"{d_val:.2f}")
                    except Exception:
                        self.barrier_distance_var.set("")

                finally:
                    self._loading = False
                    self._refresh_barrier_distance_entry_state()

                return

        self._refresh_barrier_distance_entry_state()


    def apply_barrier_fields_to_room(self, room):
        if not room:
            return

        target = self._barrier_name_from_wall(self.barrier_wall_var.get())

        for b in getattr(room, "barriers", []) or []:
            if str(getattr(b, "name", "")).strip().lower() == target.lower():
                b.material = self.barrier_material_var.get().strip() or "Pb"
                try:
                    b.thickness_mm = float(self.barrier_thickness_var.get())
                except Exception:
                    b.thickness_mm = 0.88
                try:
                    b.occupancy_factor = float(self._normalise_t_value(self.barrier_t_var.get()))
                except Exception:
                    b.occupancy_factor = 0.2
                # Distance is editable for Floor/Ceiling. Mark an explicit
                # user-entered planar distance so canonical Results/Barriers
                # refreshes preserve it rather than regenerating the default.
                # N/E/S/W distances remain geometry-owned.
                role = str(getattr(b, "barrier_role", "") or "").strip().lower()
                name = str(getattr(b, "name", "") or "").strip().lower()

                if role in {"floor", "ceiling"} or name in {"floor", "ceiling"}:
                    try:
                        b.distance_m = max(0.1, float(self.barrier_distance_var.get()))
                        b.distance_is_manual = True
                    except Exception:
                        pass
                return


    def apply_p_field_to_room(self, room):
        if not room:
            return

        try:
            p_text = str(self.p_var.get() or "").strip()
            p_val = float(p_text.split()[0])
        except Exception:
            p_val = 10.0

        selected_wall = str(self.barrier_wall_var.get()).strip()
        target_name = self._barrier_name_from_wall(selected_wall)

        for b in getattr(room, "barriers", []) or []:
            if str(getattr(b, "name", "")).strip().lower() == target_name.lower():
                b.design_goal_uSv_per_week = p_val
                break


    def on_p_changed(self, event=None):
        room = self.get_selected_room()
        if not room:
            return

        # Apply P to selected wall
        self.apply_p_field_to_room(room)

        # Trigger full recompute (important)
        if callable(self.on_change):
            self.on_change()

        # Redraw canvas immediately
        self.request_redraw()


    def _normalise_t_value(self, value) -> str:
        """Return value snapped to the nearest standard NCRP 147 T value."""
        try:
            v = float(value)
        except Exception:
            return "0.2"

        allowed = [float(x) for x in NCRP_147_T_VALUES]
        nearest = min(allowed, key=lambda x: abs(x - v))
        for raw in NCRP_147_T_VALUES:
            if abs(float(raw) - nearest) < 1e-9:
                return raw
        return "0.2"


    def _refresh_barrier_distance_entry_state(self) -> None:
        selected = str(self.barrier_wall_var.get() or "").strip().lower()

        if not hasattr(self, "barrier_distance_entry"):
            return

        if selected in {"floor", "ceiling"}:
            self.barrier_distance_entry.configure(state="normal")
        else:
            self.barrier_distance_entry.configure(state="readonly")


def apply_geometry_to_selected_room_barriers(app, room) -> None:
    """Synchronise generated room-geometry distances into the selected room barriers."""
    if room is None:
        return

    if not getattr(room, "geometry", None):
        room.geometry = app.create_default_room_geometry(room.name, room.modality)

    room.geometry.room_name = room.name
    distances = room.geometry.source_to_barrier_distances()

    existing = list(getattr(room, "barriers", []) or [])
    fallback = default_barriers()
    is_xray_room = str(getattr(room, "modality", "") or "").strip().upper() == "X-RAY"
    # Only seed the representative Fig. 5.2 wall arrangement when the room has
    # no persisted barriers yet.  Subsequent synchronisation must preserve the
    # physicist's explicit scenario assignments.
    seed_xray_fig52_roles = is_xray_room and not existing

    def find_existing(orientation: str):
        key = orientation.lower()

        if key in {"floor", "ceiling"}:
            for b in existing:
                name = str(getattr(b, "name", "")).strip().lower()
                role = str(getattr(b, "barrier_role", "")).strip().lower()
                if name == key or role == key:
                    return b
            return None

        for b in existing:
            name = str(getattr(b, "name", "")).strip().lower()
            if name.startswith(key):
                return b

        for b in fallback:
            name = str(getattr(b, "name", "")).strip().lower()
            if name.startswith(key):
                return b

        return None

    def fallback_for_orientation(orientation: str):
        key = orientation.lower()
        for barrier in fallback:
            name = str(getattr(barrier, "name", "") or "").strip().lower()
            role = str(getattr(barrier, "barrier_role", "") or "").strip().lower()
            if key in {"floor", "ceiling"}:
                if name == key or role == key:
                    return barrier
            elif name.startswith(key):
                return barrier
        return default_barriers()[0]

    new_barriers = []

    for orientation in ["N", "E", "S", "W", "Floor", "Ceiling"]:
        b = find_existing(orientation)

        if b is None:
            b = fallback_for_orientation(orientation)

        if orientation in {"N", "E", "S", "W"}:
            b.name = f"{orientation} wall"
            # XR-19B: genuinely new GXR rooms start with canonical wall construction.
            # Persisted projects are never reset here.
            if seed_xray_fig52_roles:
                b.material = "Pb"
                b.thickness_mm = 0.88
                b.material_legacy = "Pb 0.88 mm (10 kg/m2)"
            # CT-06: horizontal barrier distances are generated from room
            # geometry every time dimensions/source position change.  A prior
            # indentation error meant this assignment only ran inside the
            # Floor/Ceiling branch, leaving N/E/S/W distances stale in Results.
            b.distance_m = max(0.1, float(distances[orientation]))
        else:
            b.name = orientation
            # Preserve explicit Floor/Ceiling distances entered in Geometry.
            # Until the user provides an override, keep the existing default
            # behaviour: patient/source height is 1.0 m AFFL unless a modality
            # has supplied a transient z_m value.
            if not bool(getattr(b, "distance_is_manual", False)):
                if orientation == "Floor":
                    try:
                        source_height_m = float(getattr(room.geometry.source, "z_m", 1.0) or 1.0)
                    except Exception:
                        source_height_m = 1.0
                    b.distance_m = max(0.1, source_height_m)
                elif orientation == "Ceiling":
                    try:
                        room_height_m = float(getattr(room.geometry, "height_m", 3.0) or 3.0)
                        source_height_m = float(getattr(room.geometry.source, "z_m", 1.0) or 1.0)
                    except Exception:
                        room_height_m = 3.0
                        source_height_m = 1.0
                    b.distance_m = max(0.1, room_height_m - source_height_m)

        if is_xray_room:
            legacy_map = {
                "primary_bucky_wall": "fig52_chest_bucky_wall",
                "primary_floor": "fig52_floor_under_table",
                "secondary_wall": "fig52_secondary_wall",
                "secondary_control_booth": "fig52_control_wall",
                "secondary_door": "fig52_door",
                "floor": "fig52_floor_under_table",
                "ceiling": "fig52_ceiling",
            }
            if orientation == "Floor":
                b.barrier_role = "fig52_floor_under_table"
            elif orientation == "Ceiling":
                b.barrier_role = "fig52_ceiling"
            else:
                current_role = str(getattr(b, "barrier_role", "") or "secondary_wall").strip().lower()
                b.barrier_role = legacy_map.get(current_role, current_role)
                bucky = getattr(room.geometry, "wall_bucky", None)
                if bucky is not None and str(getattr(bucky, "wall", "") or "").upper() == orientation:
                    b.barrier_role = "fig52_chest_bucky_wall"
                elif current_role == "fig52_chest_bucky_wall":
                    # Chest-bucky role is geometry-owned.  If the receptor is
                    # moved, do not leave a stale second chest-primary wall.
                    b.barrier_role = "fig52_secondary_wall"
                elif seed_xray_fig52_roles and bucky is not None:
                    # Representative new-room default: the wall opposite the
                    # chest bucky is the cross-table / 2% primary wall.
                    # This is a starting configuration, not an inference about
                    # an existing room; users remain free to assign the actual
                    # project scenarios.
                    opposite = {"N": "S", "S": "N", "E": "W", "W": "E"}.get(
                        str(getattr(bucky, "wall", "") or "").upper()
                    )
                    if orientation == opposite:
                        b.barrier_role = "fig52_cross_table_wall"
        elif orientation == "Floor":
            b.barrier_role = "floor"
        elif orientation == "Ceiling":
            b.barrier_role = "ceiling"
        else:
            b.barrier_role = getattr(b, "barrier_role", "") or "secondary_wall"
        b.adjacent_area = getattr(b, "adjacent_area", "") or "Corridor"
        b.material = getattr(b, "material", "") or "Pb"
        b.thickness_mm = float(getattr(b, "thickness_mm", 0.88) or 0.88)
        b.occupancy_factor = float(getattr(b, "occupancy_factor", 0.2) or 0.2)
        b.design_goal_uSv_per_week = float(getattr(b, "design_goal_uSv_per_week", 10.0) or 10.0)

        app._coerce_barrier_schema(b)
        new_barriers.append(b)

    # XR-11: an optional internal operator control wall is a first-class GXR
    # barrier.  Its location is persisted in RoomGeometry and its calculation
    # distance follows the placed wall centre, consistent with the plan-view
    # preliminary-assessment geometry used elsewhere in the app.
    if is_xray_room:
        control = getattr(room.geometry, "control_wall", None)
        if control is not None:
            control_barrier = next(
                (b for b in existing if str(getattr(b, "barrier_role", "") or "") == "fig52_control_wall"
                 or str(getattr(b, "name", "") or "").strip().lower() == "control wall"),
                None,
            )
            if control_barrier is None:
                from models.shielding_models import Barrier
                control_barrier = Barrier(
                    name="Control wall", material="Pb", thickness_mm=0.88,
                    adjacent_area="Control booth", barrier_role="fig52_control_wall",
                    occupancy_factor=1.0, design_goal_uSv_per_week=100.0,
                )
            control_barrier.name = "Control wall"
            control_barrier.barrier_role = "fig52_control_wall"
            control_barrier.material = str(getattr(control, "material", "Pb") or "Pb")
            control_barrier.thickness_mm = float(getattr(control, "thickness_mm", 0.88) or 0.0)
            control_barrier.occupancy_factor = float(getattr(control, "occupancy_factor", 1.0) or 0.0)
            control_barrier.design_goal_uSv_per_week = float(getattr(control, "design_goal_uSv_per_week", 100.0) or 0.0)
            # XR-15B: distance is to the actual finite main wall segment, not
            # to the wall centre.  A zero/near-zero source-to-wall distance is
            # preserved here so the qualified solver can fail closed rather
            # than silently substituting an arbitrary calculation distance.
            control_barrier.distance_m = float(control.source_distance_m(
                room.geometry.source.x_m, room.geometry.source.y_m
            ))
            app._coerce_barrier_schema(control_barrier)
            new_barriers.append(control_barrier)

    room.barriers = new_barriers
    app.enforce_room_source_types(room)


def safe_refresh_barrier_schedule(app) -> None:
    """Refresh the barrier schedule without letting UI refresh errors break callers."""
    try:
        app._repair_invalid_source_inventory()
        app._sanitize_all_nm_patient_sources()
        app.refresh_barrier_schedule()
    except Exception as e:
        app.set_status(f"Barrier schedule not refreshed: {e}")


def geometry_changed(app) -> None:
    """Synchronise geometry edits through the central UI sync guard."""
    if getattr(app, "_geometry_sync_in_progress", False):
        return

    from services.ui_sync_guard import (
        selected_geometry_room,
        sync_geometry_source_barriers_for_room,
    )

    app._geometry_sync_in_progress = True
    try:
        room = selected_geometry_room(app)
        if room is None:
            return

        # PET dispatch persists source position beside the validated source inputs.
        # Geometry now owns that position, so update it before Results/Barriers
        # refresh. This does not revalidate transient PET source-form edits.
        if str(getattr(room, "modality", "") or "").strip().upper() == "PET":
            try:
                from services.modality_working_state import sync_pet_working_position_from_geometry

                sync_pet_working_position_from_geometry(room)
            except Exception:
                pass

        sync_geometry_source_barriers_for_room(
            app,
            room,
            update_geometry_fields=False,
            refresh_sources=True,
            refresh_barriers=True,
            refresh_results=True,
            update_status=True,
            ignore_errors=True,
        )

        # Compatibility preview hooks. Geometry is now authoritative for source
        # position in both PET and SPECT; refresh any retained preview adapter
        # only after canonical geometry/barrier/results synchronisation.
        try:
            from tabs.pet_preview_panel import refresh_pet_barrier_results_preview

            refresh_pet_barrier_results_preview(app, room=room)
        except Exception:
            pass

        if str(getattr(room, "modality", "") or "").strip().upper() == "SPECT":
            try:
                from tabs.spect_preview_panel import (
                    reset_spect_preview_position_to_room_geometry,
                    refresh_spect_preview,
                )

                reset_spect_preview_position_to_room_geometry(app, room, refresh=False)
                refresh_spect_preview(app, room)
            except Exception:
                # Compatibility preview state must never make Geometry edits fail.
                pass
    finally:
        app._geometry_sync_in_progress = False