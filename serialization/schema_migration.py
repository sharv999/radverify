CURRENT_SCHEMA_VERSION = 1

def migrate_project_schema(data: dict) -> dict:
    """
    Upgrade older .radshield project schemas to the current schema.
    """

    version = int(data.get("schema_version", 1))

    # ---------------------------------------------------------
    # V1 -> current
    # ---------------------------------------------------------

    if version == 1:
        return data

    # Unknown future schema
    raise ValueError(f"Unsupported project schema version: {version}")