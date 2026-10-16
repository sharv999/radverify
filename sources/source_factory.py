from __future__ import annotations

from models.shielding_models import Source
from modalities.registry import default_source_params_for_type, source_label_for_type


def canonical_source_name_for_type(source_type: str) -> str:
    return source_label_for_type(source_type)


class SourceFactoryMixin:

    def _canonical_source_name_for_type(self, source_type: str) -> str:
        return canonical_source_name_for_type(source_type)

    def _default_source_for_type(self, source_type: str, name: str) -> Source:
        params = default_source_params_for_type(source_type)
        if not params:
            params = {"dose_rate_uSv_h_at_1m": 100, "hours_per_week": 1}

        radiation_type = self._safe_auto_select_tvl_key(source_type, params, "")
        return Source(
            name=name,
            source_type=source_type,
            radiation_type=radiation_type,
            params=params,
        )
