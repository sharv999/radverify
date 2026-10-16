from __future__ import annotations

from typing import Any, Dict, Optional
from tkinter import messagebox
from reports.solver_reasoning_text import solver_reasoning_text as _solver_reasoning_text

from models.shielding_models import Barrier, Room


def parse_results_barrier_line(line_text: str) -> tuple[Optional[str], Optional[str]]:
    """
    Parse lines like:
      ❌ X-ray / G -> FAIL
      ⚠️ CT Room / Barrier 2 -> REVIEW
      ✅ SPECT/CT Room / North Wall -> PASS
    Returns (room_name, barrier_name) or (None, None).
    """
    text = str(line_text or "").strip()
    if not text:
        return None, None

    for prefix in ("❌ ", "⚠️ ", "✅ "):
        if text.startswith(prefix):
            text = text[len(prefix):]
            break

    if " -> " not in text or " / " not in text:
        return None, None

    lhs = text.split(" -> ", 1)[0].strip()
    if " / " not in lhs:
        return None, None

    room_name, barrier_name = lhs.split(" / ", 1)
    room_name = room_name.strip()
    barrier_name = barrier_name.strip()

    if not room_name or not barrier_name:
        return None, None

    return room_name, barrier_name


def room_barrier_from_results_text_index(
    app,
    index: str,
) -> tuple[Optional[Room], Optional[Barrier], Optional[Dict[str, Any]]]:
    if not hasattr(app, "results_text"):
        return None, None, None

    try:
        line_no = int(str(index).split(".", 1)[0])
    except Exception:
        return None, None, None

    room_name = None
    barrier_name = None

    for ln in range(line_no, 0, -1):
        try:
            text = app.results_text.get(f"{ln}.0", f"{ln}.end")
        except Exception:
            continue
        room_name, barrier_name = parse_results_barrier_line(text)
        if room_name and barrier_name:
            break

    if not room_name or not barrier_name:
        return None, None, None

    room = app.get_room_by_name(room_name)
    if room is None:
        return None, None, None

    barrier = None
    for b in room.barriers:
        if str(b.name).strip() == barrier_name:
            barrier = b
            break
    if barrier is None:
        return room, None, None

    try:
        room_results = app.get_room_barrier_results(room)
    except Exception:
        return room, barrier, None

    live = None
    for b, r in zip(room.barriers, room_results):
        if str(b.name).strip() == barrier_name:
            live = r
            break

    return room, barrier, live


def solver_help_title(solver_key: str) -> str:
    key = str(solver_key or "").strip().lower()
    if "ncrp" in key:
        return "NCRP solver"
    if "aapm" in key:
        return "AAPM solver"
    if "mu" in key:
        return "Mu + buildup solver"
    if "ct" in key:
        return "CT solver"
    return "Solver help"


def solver_help_text(room: Room, barrier: Barrier, live: Dict[str, Any]) -> str:
    solver_used = str(live.get("solver_used", "") or "").strip()
    ct_solver = str(live.get("ct_solver_used", "") or "").strip()
    dominant = str(live.get("dominant_component", "") or "").strip()
    role = str(getattr(barrier, "barrier_role", "") or "").strip()
    modality = str(getattr(room, "modality", "") or "").strip()

    key = str(solver_used or ct_solver or "").strip().lower()

    if "ncrp" in key:
        body = (
            "This solver uses an NCRP-style diagnostic X-ray shielding pathway. "
            "In plain English: it estimates the required barrier from workload, distance, "
            "occupancy and design goal, using a standard primary or secondary barrier model."
        )
    elif "aapm" in key:
        body = (
            "This solver uses an AAPM-style CT shielding pathway. "
            "In plain English: it is intended for CT scatter / secondary barrier assessment, "
            "using CT-specific workload and shielding assumptions."
        )
    elif "mu" in key:
        body = (
            "This solver uses an exponential attenuation pathway with buildup-style behaviour. "
            "In plain English: it converts the unshielded dose into a required transmission and "
            "then into required thickness using attenuation physics."
        )
    elif "ct" in key:
        body = (
            "This solver uses a CT-specific pathway. "
            "In plain English: it treats the source as CT scatter / workload driven rather than "
            "as a simple primary radiographic beam."
        )
    else:
        body = (
            "This barrier used the default solver selected from room modality and barrier role. "
            "In plain English: the app chose the most suitable physics pathway automatically."
        )

    extra = []
    if modality:
        extra.append(f"Room modality: {modality}")
    if role:
        extra.append(f"Barrier role: {role}")
    if solver_used:
        extra.append(f"Primary solver path: {solver_used}")
    if ct_solver:
        extra.append(f"CT component solver: {ct_solver}")
    if dominant:
        extra.append(f"Dominant component: {dominant}")

    if extra:
        body += "\n\n" + "\n".join(extra)

    return body


def parse_solver_reasoning_line(line_text: str) -> bool:
    return str(line_text or "").strip().startswith("Solver reasoning:")


def show_solver_help_from_results_line(app, index: str):
    room, barrier, live = room_barrier_from_results_text_index(app, index)
    if room is None or barrier is None or live is None:
        return

    solver_key = str(live.get("solver_used", "") or live.get("ct_solver_used", ""))
    title = solver_help_title(solver_key)
    body = solver_help_text(room, barrier, live)
    messagebox.showinfo(title, body)


def on_results_text_click(app, event=None):
    if not hasattr(app, "results_text"):
        return

    try:
        index = app.results_text.index(f"@{event.x},{event.y}")
        line_start = f"{index} linestart"
        line_end = f"{index} lineend"
        line_text = app.results_text.get(line_start, line_end)
    except Exception:
        return

    if parse_solver_reasoning_line(line_text):
        show_solver_help_from_results_line(app, index)
        return

    room_name, barrier_name = parse_results_barrier_line(line_text)
    if room_name and barrier_name:
        app.jump_to_barrier(room_name, barrier_name)


def solver_reasoning_text(room, barrier, live):
    return _solver_reasoning_text(room, barrier, live)
