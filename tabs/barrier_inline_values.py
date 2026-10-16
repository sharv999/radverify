"""Shared value lists for barrier inline editors.

Kept outside app.py so barrier editing does not depend on App compatibility
wrappers.
"""


def material_family_values() -> list[str]:
    return ["Pb", "Concrete", "Pb Glass"]


def xray_barrier_role_values() -> list[str]:
    return [
        "fig52_chest_bucky_wall",
        "fig52_cross_table_wall",
        "fig52_secondary_wall",
        "fig52_control_wall",
        "fig52_door",
        "fig52_darkroom_wall",
        "fig52_floor_under_table",
        "fig52_ceiling",
    ]


def commercial_pb_thicknesses() -> list[float]:
    return [
        0.44,
        0.88,
        1.32,
        1.76,
        2.20,
        2.64,
        3.08,
        3.52,
        5.28,
        7.04,
        10.56,
        14.08,
        17.60,
    ]