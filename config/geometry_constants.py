# config/geometry_constants.py

# ---------------------------------------------------------
# DEFAULT ROOM GEOMETRY
# ---------------------------------------------------------

DEFAULT_ROOM_LENGTH_M = 6.0
DEFAULT_ROOM_WIDTH_M = 4.0
DEFAULT_ROOM_HEIGHT_M = 3.6

DEFAULT_SOURCE_Y_M = DEFAULT_ROOM_LENGTH_M / 1.5
DEFAULT_SOURCE_X_M = DEFAULT_ROOM_WIDTH_M / 2.0

MIN_ROOM_DIMENSION_M = 0.5

DEFAULT_WALL_SHIELDING_HEIGHT_M = 2.1


# ---------------------------------------------------------
# SCANNER ROTATION
# ---------------------------------------------------------

DEFAULT_SCANNER_ROTATION_DEG = 0
SCANNER_ROTATION_STEP_DEG = 90


# ---------------------------------------------------------
# CT GEOMETRY
# ---------------------------------------------------------

CT_GANTRY_WIDTH_M = 2.2
CT_GANTRY_DEPTH_M = 0.9

CT_TABLE_WIDTH_M = 0.65
CT_TABLE_LENGTH_M = 2.5


# ---------------------------------------------------------
# OPENINGS
# ---------------------------------------------------------

DEFAULT_DOOR_WIDTH_M = 0.9

DEFAULT_DOOR_PB_MM = 0.0
DEFAULT_VIEWING_PANEL_PB_MM = 2.2

MIN_OPENING_WIDTH_M = 0.05


# ---------------------------------------------------------
# NCRP OCCUPANCY FACTORS
# ---------------------------------------------------------

NCRP_147_T_VALUES = (
    "1.0",
    "0.5",
    "0.2",
    "0.125",
    "0.0625",
    "0.05",
    "0.025",
)