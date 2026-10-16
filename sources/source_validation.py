from __future__ import annotations

from typing import Any, Dict, Optional

from models.shielding_models import Room
from services.source_readiness import (
    pet_working_state_output_blocking_reason,
)
from modalities.registry import (
    ct_ksec_source_types,
    default_source_type_for_modality,
    expected_source_types_for_modality,
    source_readiness_label,
    source_readiness_result_for_source,
)


class SourceValidationMixin:

    def _allowed_source_types_for_room(self, room: Optional[Room]) -> list[str]:
        if not room:
            return ["ct_scatter"]

        modality = str(getattr(room, "modality", "") or "").strip()
        mapping = self.LOCKED_MODALITY_SOURCES.get(modality)
        if mapping:
            return [stype for stype, _label in mapping]

        registry_sources = expected_source_types_for_modality(modality)
        return registry_sources or ["ct_scatter"]

    def _supported_nm_radionuclides(self) -> list[str]:
        # Compatibility wrapper for the legacy form; options are plugin-owned.
        from modalities.registry import source_form_schema_for_type

        schema = source_form_schema_for_type("nm_patient", self)
        if schema:
            for field in schema.fields:
                if field.key == "radionuclide":
                    return list(field.values)
        return []

    def _sanitize_nm_patient_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        # Compatibility wrapper; sanitisation is delegated to the source plugin.
        from modalities.registry import sanitize_source_params_for_type

        return sanitize_source_params_for_type("nm_patient", params)

    def _primary_scatter_source_type_for_room(self, room: Optional[Room]) -> str:
        default_source_type = default_source_type_for_modality(
            str(getattr(room, "modality", "") or "").strip() if room else "CT"
        )
        if default_source_type:
            return default_source_type
        allowed = self._allowed_source_types_for_room(room)
        return allowed[0] if allowed else "ct_scatter"

    # ------------------------------------------------------------------
    # CT source readiness / ksec preflight validation
    # ------------------------------------------------------------------

    def _validation_float_or_none(self, value: Any) -> float | None:
        try:
            if value in (None, ""):
                return None
            return float(value)
        except Exception:
            return None

    def _validation_status(self, errors: list[str], warnings: list[str]) -> str:
        if errors:
            return "FAIL"
        if warnings:
            return "REVIEW"
        return "PASS"

    def _ct_like_source_types(self) -> set[str]:
        return set(ct_ksec_source_types())

    def validate_ct_source_readiness(self, src: Any, room: Optional[Room] = None) -> Dict[str, Any]:
        """
        Validate source readiness via the registered modality source validator.

        The CT ksec/manual-override rules live in ``modalities.ct``; this mixin
        keeps the legacy app method as a compatibility wrapper.
        """
        source_type = str(getattr(src, "source_type", "") or "").strip()
        params = getattr(src, "params", {}) or {}
        if not isinstance(params, dict):
            params = {}

        context = {
            "room_name": str(getattr(room, "name", "") or getattr(src, "room_name", "") or ""),
            "room_modality": str(getattr(room, "modality", "") or ""),
            "source_name": str(getattr(src, "name", "") or ""),
            "radiation_type": str(getattr(src, "radiation_type", "") or params.get("tvl_key", "") or "").strip(),
        }
        result = source_readiness_result_for_source(source_type, params, context)
        if result is not None:
            # Legacy app callers historically expected this boolean flag.
            result.setdefault("is_ct_like", source_type in self._ct_like_source_types())
            return result

        checks: list[Dict[str, str]] = []
        checks.append({
            "name": source_readiness_label(source_type, "source_type", "Source type"),
            "status": "INFO",
            "detail": f"Not a CT scatter source: {source_type or 'blank'}",
        })
        return {
            "overall_status": "PASS",
            "is_ct_like": False,
            "source_type": source_type,
            "room_name": context["room_name"],
            "source_name": context["source_name"],
            "checks": checks,
            "errors": [],
            "warnings": [],
            "blocking": False,
            "ksec_basis": "not_applicable",
        }

    def validate_room_source_readiness(self, room: Optional[Room]) -> Dict[str, Any]:
        """
        Validate all sources in a room, with special handling for CT-like sources.
        """
        room_name = str(getattr(room, "name", "") or "") if room else ""
        results: list[Dict[str, Any]] = []
        errors: list[str] = []
        warnings: list[str] = []

        if not room:
            return {
                "overall_status": "FAIL",
                "room_name": "",
                "source_results": [],
                "errors": ["No room selected."],
                "warnings": [],
                "blocking": True,
            }

        try:
            sources = list(self.get_sources_for_room(room.name))
        except Exception:
            sources = list(getattr(room, "sources", []) or [])

        pet_output_reason = pet_working_state_output_blocking_reason(room)
        if pet_output_reason:
            warnings.append(f"{room_name}: {pet_output_reason}" if room_name else pet_output_reason)

        if not sources:
            errors.append("Room has no sources.")

        for src in sources:
            if str(getattr(src, "source_type", "") or "").strip() in self._ct_like_source_types():
                result = self.validate_ct_source_readiness(src, room)
            else:
                result = self.validate_ct_source_readiness(src, room)

            results.append(result)
            errors.extend(result.get("errors", []) or [])
            warnings.extend(result.get("warnings", []) or [])

        if pet_output_reason and not any(bool(item.get("output_blocking", False)) for item in results):
            results.append({
                "overall_status": "REVIEW",
                "status": "REVIEW",
                "source_type": "persisted_pet_working_state",
                "room_name": room_name,
                "source_name": "Persisted PET working state",
                "checks": [],
                "errors": [],
                "warnings": [f"{room_name}: {pet_output_reason}" if room_name else pet_output_reason],
                "blocking": False,
                "output_blocking": True,
                "basis": "production_host_results_only",
                "message": pet_output_reason,
            })

        overall_status = self._validation_status(errors, warnings)

        return {
            "overall_status": overall_status,
            "room_name": room_name,
            "source_results": results,
            "errors": errors,
            "warnings": warnings,
            "blocking": bool(errors),
        }

    def validate_project_source_readiness(self) -> Dict[str, Any]:
        """
        Validate source readiness across the entire project.
        """
        room_results: list[Dict[str, Any]] = []
        errors: list[str] = []
        warnings: list[str] = []

        project = getattr(self, "project", None)
        rooms = list(getattr(project, "rooms", []) or [])

        if not rooms:
            errors.append("Project has no rooms.")

        for room in rooms:
            result = self.validate_room_source_readiness(room)
            room_results.append(result)
            errors.extend(result.get("errors", []) or [])
            warnings.extend(result.get("warnings", []) or [])

        overall_status = self._validation_status(errors, warnings)

        return {
            "overall_status": overall_status,
            "room_results": room_results,
            "errors": errors,
            "warnings": warnings,
            "blocking": bool(errors),
        }

    def source_readiness_summary_lines(self, validation: Dict[str, Any] | None = None) -> list[str]:
        """
        Return human-readable preflight lines suitable for a Results panel,
        status panel, report appendix, or prompt.
        """
        validation = validation or self.validate_project_source_readiness()
        lines = [f"Source readiness: {validation.get('overall_status', 'UNKNOWN')}"]

        for room_result in validation.get("room_results", []) or []:
            room_name = room_result.get("room_name", "")
            lines.append(f"Room: {room_name or 'Unknown'} — {room_result.get('overall_status', 'UNKNOWN')}")

            for source_result in room_result.get("source_results", []) or []:
                source_name = source_result.get("source_name", "") or source_result.get("source_type", "Source")
                lines.append(f"  Source: {source_name} — {source_result.get('overall_status', 'UNKNOWN')}")

                for check in source_result.get("checks", []) or []:
                    symbol = "✅"
                    if check.get("status") == "FAIL":
                        symbol = "❌"
                    elif check.get("status") == "REVIEW":
                        symbol = "⚠️"
                    elif check.get("status") == "INFO":
                        symbol = "ℹ️"

                    detail = str(check.get("detail", "") or "").strip()
                    suffix = f": {detail}" if detail else ""
                    lines.append(f"    {symbol} {check.get('name', 'Check')}{suffix}")

        return lines
