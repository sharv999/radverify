def normalize_source_params(source_type: str, params: dict) -> dict:
    """
    Global normalisation engine.
    - Preserves valid user input
    - Fills missing values
    - Enforces types
    """

    SOURCE_PARAM_SCHEMAS = {
        "ct_scatter": {
            "scans_per_week": {"default": 60, "type": float},
            "workload_mAs_per_scan": {"default": 630, "type": float},
        },

        "spect_ct_secondary_scatter": {
            "scans_per_week": {"default": 60, "type": float},
            "workload_mAs_per_scan": {"default": 630, "type": float},
        },

        "nm_patient": {
            "NMPS_R": {"default": 20, "type": float},
            "NMPS_S": {"default": 20, "type": float},
            "NBONE": {"default": 40, "type": float},
            "AMPS_R": {"default": 350, "type": float},
            "AMPS_S": {"default": 1000, "type": float},
        },

        "xray_primary": {
            "exposures_per_week": {"default": 200, "type": float},
            "mAs_per_exposure": {"default": 10, "type": float},
        },
    }
    schema = SOURCE_PARAM_SCHEMAS.get(source_type, {})

    if not isinstance(params, dict):
        params = {}

    normalized = dict(params)  # start with existing values

    # Ksec is special: NULL/blank is meaningful for vendor records that are
    # still pending. Preserve it so the calculation layer can block final output
    # instead of silently inserting a generic default.
    if source_type in ("ct_scatter", "spect_ct_secondary_scatter"):
        ksec_key = "ksec_mGy_per_100mAs_at_1m"
        if ksec_key in normalized:
            val = normalized.get(ksec_key)
            if val in (None, "", "NULL", "null", "None"):
                normalized[ksec_key] = ""
            else:
                try:
                    value = float(val)
                    normalized[ksec_key] = value if value > 0 else ""
                except (ValueError, TypeError):
                    normalized[ksec_key] = ""

    for key, meta in schema.items():
        default = meta["default"]
        dtype = meta["type"]

        val = normalized.get(key)

        if val in (None, ""):
            normalized[key] = default
            continue

        try:
            normalized[key] = dtype(val)
        except (ValueError, TypeError):
            normalized[key] = default

    return normalized