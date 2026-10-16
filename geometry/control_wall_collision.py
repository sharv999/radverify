"""Plan-view GXR source/control-wall collision checks (metres)."""
from __future__ import annotations

import math


def control_wall_segments(wall):
    """Return the main wall and two 45-degree nibs in room coordinates."""
    x, y = float(wall.center_x_m), float(wall.center_y_m)
    angle = math.radians(float(wall.orientation_deg))
    ux, uy = math.cos(angle), math.sin(angle)
    nx, ny = uy, -ux  # canvas normal converted back to room coordinates
    half = max(0.1, float(wall.length_m)) / 2
    a = (x - ux * half, y - uy * half)
    b = (x + ux * half, y + uy * half)
    nib = max(0.0, float(getattr(wall, 'nib_length_m', 0.75)))
    if nib == 0:
        return ((a, b),)
    c = math.sqrt(0.5)
    return ((a, b),
            (a, (a[0] + nib * (-ux*c - nx*c), a[1] + nib * (-uy*c - ny*c))),
            (b, (b[0] + nib * ( ux*c - nx*c), b[1] + nib * ( uy*c - ny*c))))


def _orient(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def _on_segment(a, b, p, tol=1e-9):
    return (abs(_orient(a,b,p)) <= tol and
            min(a[0],b[0])-tol <= p[0] <= max(a[0],b[0])+tol and
            min(a[1],b[1])-tol <= p[1] <= max(a[1],b[1])+tol)


def segments_intersect(a, b, c, d):
    o1, o2, o3, o4 = _orient(a,b,c), _orient(a,b,d), _orient(c,d,a), _orient(c,d,b)
    if ((o1 > 1e-9 and o2 < -1e-9) or (o1 < -1e-9 and o2 > 1e-9)) and ((o3 > 1e-9 and o4 < -1e-9) or (o3 < -1e-9 and o4 > 1e-9)):
        return True
    return any((_on_segment(a,b,c), _on_segment(a,b,d), _on_segment(c,d,a), _on_segment(c,d,b)))


def point_on_control_wall(point, wall):
    return any(_on_segment(a,b,point) for a,b in control_wall_segments(wall))


def source_path_crosses_control_wall(start, end, wall):
    # A legacy project may already place the source on the wall. Permit an
    # outward escape, but not movement along the wall or across another segment.
    if point_on_control_wall(start, wall) and not point_on_control_wall(end, wall):
        fraction = 1e-6
        escaped = (start[0] + fraction * (end[0] - start[0]),
                   start[1] + fraction * (end[1] - start[1]))
        if not point_on_control_wall(escaped, wall):
            start = escaped
    return any(segments_intersect(start,end,a,b) for a,b in control_wall_segments(wall))
