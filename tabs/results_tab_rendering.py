from __future__ import annotations

from typing import Any, Dict, Optional
from engine.design_constraints import build_room_constraint_summary
from tabs.barrier_risk_ui import (
    barrier_heatmap_color,
    classify_barrier_visual_state,
    derive_primary_barrier_issue,
)
from tabs.results_tab_help import solver_reasoning_text
from services.barriers_modality_context import barriers_modality_context
from tabs.results_tab_text import dominant_source_text
from services.calculation_display_state import room_calculation_display_state
from services.source_readiness import room_has_persisted_pet_working_state
from services.pet_results_presentation_contract import (
    pet_results_error_text,
    pet_results_risk_error_text,
    pet_results_room_lines,
)
from services.spect_results_model import room_has_persisted_spect_working_state
from services.spect_results_presentation_contract import (
    spect_results_error_text,
    spect_results_room_lines,
)
from tabs.barrier_live_results import (
    display_recommended_thickness_mm,
    display_required_thickness_mm,
    get_barrier_live_result,
)
from services.opening_physics import opening_live_result
from tabs.barriers_openings import insert_opening_physics_rows
from tabs.barrier_table_formatting import format_barrier_table_cell


def result_status_from_live(live: Dict[str, Any]) -> str:
    """
    Results-tab display status.

    Keep Results tab aligned with Geometry and Barriers display status:
      FAIL / negative margin        -> FAIL
      PASS with margin < 0.5 mm     -> REVIEW
      PASS with margin >= 0.5 mm    -> PASS
    """
    if not isinstance(live, dict):
        live = {}

    status = str(
        live.get("compliance_status")
        or live.get("status")
        or ""
    ).strip().upper()

    try:
        margin_mm = float(live.get("margin_mm", 0.0) or 0.0)
    except Exception:
        margin_mm = 0.0

    if status in {"FAIL", "ERROR", "NON-COMPLIANT"} or margin_mm < 0:
        return "FAIL"

    if status in {"REVIEW", "WARN", "WARNING"} or margin_mm < 0.5:
        return "REVIEW"

    return "PASS"


def result_symbol_and_tag(status: str) -> tuple[str, str]:
    status = str(status or "").strip().upper()

    if status == "FAIL":
        return "❌", "result_fail"

    if status == "REVIEW":
        return "⚠️", "result_review"

    return "✅", "result_pass"


def user_facing_status_from_visual_risk(live: Dict[str, Any], visual_risk: str) -> str:
    """Return the status shown to users in live tables/results.

    Physics compliance_status remains available in the live result, but the
    visible status must align with the same visual risk state used for row
    colour and the Results text.  This prevents borderline PASS calculations
    from appearing contradictory when the review rule promotes them to REVIEW.
    """
    risk = str(visual_risk or "").strip().upper()
    if risk in {"FAIL", "REVIEW"}:
        return risk

    status = str((live or {}).get("compliance_status", "") or "").strip().upper()
    if status in {"FAIL", "ERROR", "NON-COMPLIANT"}:
        return "FAIL"
    if status in {"REVIEW", "WARN", "WARNING"}:
        return "REVIEW"
    if status == "PASS":
        return "PASS"
    return status


def _sync_barriers_modality_context(app, room) -> None:
    """Keep Barriers-tab energy/solver provenance aligned with room modality."""
    context = barriers_modality_context(
        room,
        current_solver_mode=str(
            getattr(app, "solver_mode_var", None).get()
            if hasattr(app, "solver_mode_var") else "auto"
        ),
    )
    if hasattr(app, "results_energy_basis_var"):
        app.results_energy_basis_var.set(context.energy_basis_display)
    if hasattr(app, "barriers_solver_display_var"):
        app.barriers_solver_display_var.set(context.solver_display)
    combo = getattr(app, "barriers_solver_combo", None)
    if combo is not None:
        if context.solver_editable:
            from engine.shielding_engine import SOLVER_MODE_OPTIONS
            combo.configure(values=SOLVER_MODE_OPTIONS, state="readonly")
        else:
            combo.configure(values=(context.solver_display,), state="readonly")


def refresh_barrier_schedule(app):
    app._repair_invalid_source_inventory()
    app._sanitize_all_nm_patient_sources()

    if not hasattr(app, "barrier_table"):
        return

    room_name = app.barriers_room_var.get().strip()
    if not room_name and app.project.rooms:
        room_name = app.project.rooms[0].name
        app.barriers_room_var.set(room_name)

    for item in app.barrier_table.get_children():
        app.barrier_table.delete(item)

    room = app.get_room_by_name(room_name)
    if not room:
        if hasattr(app, "barrier_risk_summary_var"):
            app.barrier_risk_summary_var.set("No barrier risk data yet.")
        if hasattr(app, "barrier_risk_table"):
            for item in app.barrier_risk_table.get_children():
                app.barrier_risk_table.delete(item)
        return

    _sync_barriers_modality_context(app, room)
    app._apply_geometry_to_selected_room_barriers(room)

    display_state = room_calculation_display_state(app, room)
    if display_state.blocking:
        if hasattr(app, "barrier_risk_table"):
            for item in app.barrier_risk_table.get_children():
                app.barrier_risk_table.delete(item)
        if hasattr(app, "barrier_risk_summary_var"):
            app.barrier_risk_summary_var.set(display_state.message)
        try:
            app.set_status(display_state.message)
        except Exception:
            pass
        return

    try:
        # Barriers is a presentation of the same canonical Results model used by
        # Geometry and Results. PET/SPECT must not fall back through the CT/generic
        # barrier calculator once their persisted production state exists.
        room_results = app.get_room_results_model(room)

        if not room_results and room.barriers:
            has_patient_source_results = (
                room_has_persisted_pet_working_state(room)
                or room_has_persisted_spect_working_state(room)
            )
            if not has_patient_source_results:
                room_results = [get_barrier_live_result(app, room, b) for b in room.barriers]

    except Exception as e:
        app.set_status(f"Barrier schedule unavailable: {e}")
        return

    from reports.barrier_schedule import build_canonical_barrier_schedule_payload

    try:
        schedule_rows = build_canonical_barrier_schedule_payload(
            app,
            room,
            room_results=room_results,
        )
    except Exception as exc:
        app.set_status(f"Barrier schedule payload unavailable: {exc}")
        return

    for row in schedule_rows:
        values = [format_barrier_table_cell(row, col) for col in app.BARRIER_COLUMNS]

        status = str(row.get("compliance_status") or row.get("status") or "").strip().upper()
        row_confidence = row.get("confidence", 1.0)

        if app.heatmap_mode_var.get():
            color = barrier_heatmap_color(app, row, row_confidence)
            tag = f"heat_{color}"
            try:
                app.barrier_table.tag_configure(tag, background=color)
            except Exception:
                pass
        elif status == "FAIL":
            tag = "qa_fail"
        elif status == "REVIEW":
            tag = "qa_review"
        else:
            tag = "qa_pass"

        app.barrier_table.insert("", "end", values=values, tags=(tag,))

    # Force risk panel to populate on startup / refresh
    try:
        app.render_barrier_risk_panel(room, room_results)
    except Exception as exc:
        app.barrier_risk_summary_var.set(f"Barrier risk panel error: {exc}")

    app.refresh_results_tab()


def render_barrier_risk_panel(app, room: Optional[Room], room_results: list[Dict[str, Any]] | None = None):
    if not hasattr(app, "barrier_risk_table"):
        return

    for item in app.barrier_risk_table.get_children():
        app.barrier_risk_table.delete(item)

    if not room:
        if hasattr(app, "barrier_risk_summary_var"):
            app.barrier_risk_summary_var.set("No barrier risk data yet.")
        return

    display_state = room_calculation_display_state(app, room)
    if display_state.blocking:
        if hasattr(app, "barrier_risk_summary_var"):
            app.barrier_risk_summary_var.set(display_state.message)
        return

    # Always rebuild live results here so the risk panel never depends on caller state
    try:
        room_results = app.get_room_results_model(room)
    except Exception as exc:
        if room_has_persisted_pet_working_state(room):
            app.barrier_risk_summary_var.set(pet_results_risk_error_text(exc))
            return
        room_results = []

    room_results = room_results or []

    # Fallback: calculate per barrier if table function returned nothing
    if not room_results:
        fallback_results = []
        for barrier in getattr(room, "barriers", []) or []:
            try:
                fallback_results.append(get_barrier_live_result(app, room, barrier))
            except Exception:
                fallback_results.append({})
        room_results = fallback_results

    if not room_results:
        if hasattr(app, "barrier_risk_summary_var"):
            app.barrier_risk_summary_var.set(f"{room.name} | No barrier risk data yet.")
        return

    total = len(room_results)
    fail_count = 0
    review_count = 0
    pass_count = 0

    rows = []
    for barrier, live in zip(room.barriers, room_results):
        barrier_name = str(barrier.name)
        confidence = app._row_confidence_from_live(barrier_name, live)
        live_status = str(live.get("compliance_status", "")).upper().strip()
        margin_mm = app._safe_float(live.get("margin_mm"), 0.0)
        required_mm = live.get("required_thickness_mm", "")
        actual_mm = getattr(barrier, "thickness_mm", "")
        severities: set[str] = set()
        mismatch_flag = False
        primary_issue = derive_primary_barrier_issue(app, barrier, live, [])

         # Keep risk-panel colours aligned with the live barrier table:
        # red = fail / negative margin / critical uncertainty
        # amber = borderline margin / review / moderate confidence
        # green = comfortable pass / strong confidence
        risk, base_tag = classify_barrier_visual_state(
            app,
            live=live,
            confidence=confidence,
            severities=severities,
            mismatch_flag=mismatch_flag,
        )

        if (
            live_status in {"FAIL", "ERROR", "NON-COMPLIANT"}
            or margin_mm < 0
            or "critical" in severities
            or confidence < 0.75
        ):
            risk = "FAIL"
            tag = "risk_fail"
            fail_count += 1
        elif (
            live_status in {"REVIEW", "WARN", "WARNING"}
            or "warning" in severities
            or mismatch_flag
            or margin_mm < 0.5
            or confidence < 0.90
        ):
            risk = "REVIEW"
            tag = "risk_review"
            review_count += 1
        else:
            risk = "PASS"
            tag = "risk_pass"
            pass_count += 1

        rows.append((
            0 if risk == "FAIL" else 1 if risk == "REVIEW" else 2,
            confidence,
            barrier_name,
            risk,
            tag,
            required_mm,
            f"{actual_mm:.2f}" if str(barrier.material) == "Pb" else actual_mm,
            margin_mm,
            primary_issue,
        ))

    # Include opening sub-barriers: doors and viewing panels
    geom = getattr(room, "geometry", None)
    if geom:
        for opening_index, opening in enumerate(getattr(geom, "openings", []) or [], start=1):
            opening_barrier, live = opening_live_result(app, room, opening, opening_index)
            if opening_barrier is None or not live:
                continue

            barrier_name = str(opening_barrier.name)
            confidence = app._row_confidence_from_live(barrier_name, live)
            live_status = str(live.get("compliance_status", "")).upper().strip()
            margin_mm = app._safe_float(live.get("margin_mm"), 0.0)
            required_mm = live.get("required_thickness_mm", "")
            actual_mm = getattr(opening_barrier, "thickness_mm", "")
            primary_issue = derive_primary_barrier_issue(app, opening_barrier, live, [])

            if live_status in {"FAIL", "ERROR", "NON-COMPLIANT"} or margin_mm < 0 or confidence < 0.75:
                risk = "FAIL"
                tag = "risk_fail"
                fail_count += 1
            elif live_status in {"REVIEW", "WARN", "WARNING"} or margin_mm < 0.5 or confidence < 0.90:
                risk = "REVIEW"
                tag = "risk_review"
                review_count += 1
            else:
                risk = "PASS"
                tag = "risk_pass"
                pass_count += 1

            rows.append((
                0 if risk == "FAIL" else 1 if risk == "REVIEW" else 2,
                confidence,
                barrier_name,
                risk,
                tag,
                required_mm,
                f"{actual_mm:.2f}" if str(opening_barrier.material) in {"Pb", "Pb glass"} else actual_mm,
                margin_mm,
                primary_issue,
            ))


    # sort by risk first, then confidence
    rows.sort(key=lambda x: (x[0], x[1]))

    for idx, row in enumerate(rows):
        _, confidence, barrier_name, risk, tag, required_mm, actual_mm, margin_mm, primary_issue = row
        app.barrier_risk_table.insert(
            "",
            "end",
            iid=str(idx),
            values=(
                barrier_name,
                risk,
                f"{confidence:.2f}",
                required_mm,
                actual_mm,
                f"{margin_mm:.3f}",
                primary_issue,
            ),
            tags=(tag,),
        )

    row_confidences = [app._row_confidence_from_live(b.name, live) for b, live in zip(room.barriers, room_results)]
    avg_conf = sum(row_confidences) / len(row_confidences) if row_confidences else 1.0
    if hasattr(app, "barrier_risk_summary_var"):
        app.barrier_risk_summary_var.set(
            f"{room.name} | Avg confidence {avg_conf:.2f} | Fail: {fail_count} | Review: {review_count} | Pass: {pass_count}"
        )


def build_live_results_lines(app) -> list[tuple[str, Optional[str]]]:
    lines: list[tuple[str, Optional[str]]] = []

    lines.append(("Shielding Results Summary", "result_heading"))
    lines.append(("=========================", "result_heading"))
    lines.append(("", None))

    # -------------------------------------------------------------
    # Source readiness preflight summary
    # -------------------------------------------------------------
    if hasattr(app, "source_readiness_summary_lines"):
        try:
            readiness_lines = app.source_readiness_summary_lines()
        except Exception as exc:
            readiness_lines = [f"Source readiness preflight unavailable: {exc}"]

        if readiness_lines:
            lines.append(("Source Readiness Preflight", "result_heading"))
            lines.append(("--------------------------", "muted"))

            for line in readiness_lines:
                text_line = str(line)
                stripped = text_line.strip()
                if stripped.startswith("❌"):
                    tag = "result_fail"
                elif stripped.startswith("⚠️"):
                    tag = "result_review"
                elif stripped.startswith("✅"):
                    tag = "result_pass"
                else:
                    tag = "muted"
                lines.append((text_line, tag))

            lines.append(("", None))

    for room in app.project.rooms:
        summary = build_room_constraint_summary(room.modality) or {}

        expected_source_list = summary.get("expected_source_types")
        if not isinstance(expected_source_list, (list, tuple)):
            expected_source_list = []

        expected_sources = ", ".join(str(x) for x in expected_source_list if x)
        basis_parts = [
            f"Room class: {summary.get('classification', '')}",
            f"Design energy: {summary.get('default_energy_label', '')}",
            f"Solver: {summary.get('default_solver_mode', '')}",
        ]
        if expected_sources:
            basis_parts.append(f"Sources: {expected_sources}")

        lines.append((f"{room.name}", "result_heading"))
        lines.append((f"  Basis: {' | '.join(basis_parts)}", "muted"))
        lines.append(("", None))

        try:
            room_results = app.get_room_results_model(room)
        except Exception as e:
            if room_has_persisted_pet_working_state(room):
                lines.append((pet_results_error_text(e), "result_fail"))
            elif room_has_persisted_spect_working_state(room):
                lines.append((spect_results_error_text(e), "result_fail"))
            else:
                lines.append((f"  ERROR generating room results: {e}", "result_fail"))
            lines.append(("", None))
            continue

        room_results = room_results or []
        if room_has_persisted_pet_working_state(room):
            lines.extend(pet_results_room_lines(room.name, room_results))
            lines.append(("", None))
            continue
        if room_has_persisted_spect_working_state(room):
            lines.extend(spect_results_room_lines(room.name, room_results))
            lines.append(("", None))
            continue

        # =========================
        # WALLS
        # =========================

        for i, barrier in enumerate(room.barriers):
            live = room_results[i] if i < len(room_results) else {}

            if not isinstance(live, dict):
                live = {}

            status = str(live.get("compliance_status", "")).strip().upper()
            confidence = app._row_confidence_from_live(barrier.name, live)

            severities: set[str] = set()
            mismatch_flag = bool(live.get("material_mismatch_flag", False))

            status = result_status_from_live(live)
            symbol, status_tag = result_symbol_and_tag(status)
            risk = status

            lines.append((f"{symbol} {room.name} / {barrier.name} -> {risk}", status_tag))
            lines.append(("", None))

            material = str(getattr(barrier, "material", "")).strip()
            thickness_mm = app._safe_float_or_none(getattr(barrier, "thickness_mm", None))

            req_pb = app._safe_float_or_none(live.get("required_lead_mm"))
            req_conc = app._safe_float_or_none(live.get("required_concrete_mm"))
            margin_mm = app._safe_float_or_none(live.get("margin_mm"))

            unshielded = app._safe_float_or_none(live.get("unshielded_weekly_dose_uSv")) or 0.0
            contributions = live.get("source_contributions", "")
            notes = str(live.get("notes", "") or "").strip()

            dominant_source = dominant_source_text(room, barrier, live)
            dominant_reason = app._dominant_reason_text(contributions)
            solver_reason = solver_reasoning_text(room, barrier, live)

            lines.append(("", None))
            lines.append((f"  Unshielded weekly dose: {unshielded:.3f} uSv/week", None))
            lines.append((f"  Provided shielding: {app._fmt_material_with_mm(material, thickness_mm)}", None))

            if material == "Pb":
                lines.append((f"  Required shielding: Pb {app._fmt_mm(req_pb, 2)}", None))
            elif material == "Concrete":
                lines.append((f"  Required shielding: Concrete {app._fmt_mm(req_conc, 1)}", None))
            else:
                lines.append((f"  Required shielding: Pb {app._fmt_mm(req_pb, 2)} | Concrete {app._fmt_mm(req_conc, 1)}", None))

            if margin_mm is not None:
                if margin_mm < 0:
                    lines.append((f"  Shortfall: {abs(margin_mm):.3f} mm", status_tag))
                else:
                    lines.append((f"  Margin: {margin_mm:.3f} mm", None))

            lines.append((f"  Dominant source: {dominant_source}", None))
            if dominant_reason:
                lines.append((f"  Reason: {dominant_reason}", "muted"))

            lines.append((f"  Solver reasoning: {solver_reason}", "muted"))

            if notes:
                lines.append((f"  Notes: {notes}", "muted"))

            lines.append(("", None))


        # =========================
        # OPENINGS  ✅ NOW CORRECT
        # =========================
        geom = getattr(room, "geometry", None)

        if geom and getattr(geom, "openings", None):
            lines.append(("", None))
            lines.append(("  Openings", "muted"))
            lines.append(("", None))

            for opening_index, opening in enumerate(getattr(geom, "openings", []) or [], start=1):
                result = opening_live_result(app, room, opening, opening_index)

                if not result:
                    continue

                opening_barrier, live = result

                if opening_barrier is None or not isinstance(live, dict):
                    continue

                barrier = opening_barrier
                confidence = app._row_confidence_from_live(barrier.name, live)

                status = result_status_from_live(live)
                symbol, status_tag = result_symbol_and_tag(status)
                risk = status

                lines.append((f"{symbol} {room.name} / {barrier.name} -> {risk}", status_tag))
                lines.append(("", None))

                material = str(getattr(barrier, "material", "")).strip()
                thickness_mm = app._safe_float_or_none(getattr(barrier, "thickness_mm", None))
                req_pb = app._safe_float_or_none(live.get("required_lead_mm"))
                req_conc = app._safe_float_or_none(live.get("required_concrete_mm"))
                margin_mm = app._safe_float_or_none(live.get("margin_mm"))
                unshielded = app._safe_float_or_none(live.get("unshielded_weekly_dose_uSv")) or 0.0
                notes = str(live.get("notes", "") or "").strip()

                dominant_source = dominant_source_text(room, barrier, live)
                solver_reason = solver_reasoning_text(room, barrier, live)

                lines.append((f"  Unshielded weekly dose: {unshielded:.3f} uSv/week", None))
                lines.append((f"  Provided shielding: {app._fmt_material_with_mm(material, thickness_mm)}", None))

                if material == "Pb glass":
                    lines.append((f"  Required shielding: Pb glass equivalent {app._fmt_mm(req_pb, 2)}", None))
                elif material == "Pb":
                    lines.append((f"  Required shielding: Pb {app._fmt_mm(req_pb, 2)}", None))
                elif material == "Concrete":
                    lines.append((f"  Required shielding: Concrete {app._fmt_mm(req_conc, 1)}", None))
                else:
                    lines.append((f"  Required shielding: Pb {app._fmt_mm(req_pb, 2)}", None))

                if margin_mm is not None:
                    if margin_mm < 0:
                        lines.append((f"  Shortfall: {abs(margin_mm):.3f} mm", status_tag))
                    else:
                        lines.append((f"  Margin: {margin_mm:.3f} mm", None))

                lines.append((f"  Dominant source: {dominant_source}", None))
                lines.append((f"  Solver reasoning: {solver_reason}", "muted"))

                if notes:
                    lines.append((f"  Notes: {notes}", "muted"))

                lines.append(("", None))

    return lines


def refresh_results_tab(app):
    if not hasattr(app, "results_text"):
        return

    app.results_text.configure(state="normal")
    app.results_text.delete("1.0", "end")

    try:
        lines = app._build_live_results_lines()

        for text, tag in lines:
            tags = []
            if tag:
                tags.append(tag)

            stripped = str(text).strip()
            if stripped.startswith(("❌ ", "⚠️ ", "✅ ")) and " / " in stripped and " -> " in stripped:
                tags.append("result_clickable")

            if stripped.startswith("Solver reasoning:") or stripped.startswith("  Solver reasoning:"):
                tags.append("result_clickable")

            text_str = str(text)

            if "**" in text_str:
                parts = text_str.split("**")
                for i, part in enumerate(parts):
                    part_tags = tuple(tags)
                    if i % 2 == 1:
                        part_tags = tuple(list(tags) + ["dominant"])
                    if part_tags:
                        app.results_text.insert("end", part, part_tags)
                    else:
                        app.results_text.insert("end", part)
                app.results_text.insert("end", "\n")
            else:
                if tags:
                    app.results_text.insert("end", text_str + "\n", tuple(tags))
                else:
                    app.results_text.insert("end", text_str + "\n")

    except Exception as e:
        app.results_text.insert("1.0", f"Could not build live results: {e}\n", "result_fail")

    app.results_text.configure(state="disabled")



def row_confidence_from_live(app, barrier_name: str, live: Dict[str, Any]) -> float:
    # Deterministic confidence derived from the calculation result itself.
    # This deliberately has no dependency on the removed AI-QC subsystem.
    conf = 1.0

    compliance = str(live.get("compliance_status", "")).strip().upper()
    solver_used = str(live.get("solver_used", "") or "").strip().lower()

    try:
        margin_mm = float(live.get("margin_mm", 0.0) or 0.0)
    except Exception:
        margin_mm = 0.0

    try:
        required_mm = float(live.get("required_thickness_mm", 0.0) or 0.0)
    except Exception:
        required_mm = 0.0

    # -----------------------------
    # 1) Physics margin adjustment
    # -----------------------------
    # Strong positive margin -> higher confidence
    # Borderline -> amber territory
    # Negative margin -> low confidence
    if margin_mm < 0:
        deficit = abs(margin_mm)
        if deficit >= 5.0:
            conf -= 0.40
        elif deficit >= 1.0:
            conf -= 0.30
        else:
            conf -= 0.20
    else:
        # positive margin
        if margin_mm >= 5.0:
            conf += 0.08
        elif margin_mm >= 1.0:
            conf += 0.04
        elif required_mm > 0 and margin_mm < 0.5:
            conf -= 0.12
        elif required_mm > 0 and margin_mm < 1.0:
            conf -= 0.06

    # --------------------------------
    # 2) Solver quality / trust signal
    # --------------------------------
    # Higher trust for direct domain-specific solvers,
    # lower trust for fallback / generic paths.
    if "ncrp_primary" in solver_used:
        conf += 0.05
    elif "ncrp_ct_secondary" in solver_used:
        conf += 0.05
    elif "mu_plus_buildup" in solver_used:
        conf -= 0.10
    elif solver_used in {"", "unknown"}:
        conf -= 0.10

    # --------------------------------
    # 3) Compliance status adjustment
    # --------------------------------
    if compliance in {"FAIL", "NON-COMPLIANT", "ERROR"}:
        conf = min(conf, 0.35)
    elif compliance in {"REVIEW", "WARN", "WARNING"}:
        conf = min(conf, 0.75)
    elif compliance == "PASS":
        conf = min(1.0, conf)

    # Clamp
    conf = max(0.0, min(1.0, conf))
    return round(conf, 2)

    def _status_text(status):
        s = str(status).upper()

        if s in {"FAIL", "ERROR", "NON-COMPLIANT"}:
            return "FAIL (exceeds design goal)"
        if s in {"REVIEW", "WARN"}:
            return "REVIEW (check assumptions)"
        return "PASS (meets design goal)"
