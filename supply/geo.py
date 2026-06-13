"""Geospatial helpers for port geofencing.

Pure functions with no Django dependency so they are trivial to unit-test.
Ports are passed in as lightweight ``PortGeo`` tuples built once from the
``Port`` queryset (see ``load_port_geos``) rather than touching the ORM here.
"""

import math
from typing import NamedTuple, Optional, Sequence

EARTH_RADIUS_NM = 3440.065  # mean earth radius in nautical miles


class PortGeo(NamedTuple):
    id: int
    name: str
    latitude: float
    longitude: float
    radius_nm: float
    port_type: str  # 'load' | 'discharge' | 'both'


def haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points, in nautical miles."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_NM * math.asin(min(1.0, math.sqrt(a)))


def find_containing_port(
    lat: float, lon: float, ports: Sequence[PortGeo]
) -> Optional[PortGeo]:
    """Return the nearest port whose geofence contains the point, or None.

    Linear scan; fine for the few dozen ports we track. If two geofences
    overlap, the closer port wins.
    """
    best = None
    best_dist = None
    for port in ports:
        dist = haversine_nm(lat, lon, port.latitude, port.longitude)
        if dist <= port.radius_nm and (best_dist is None or dist < best_dist):
            best = port
            best_dist = dist
    return best


def is_departed(
    lat: float, lon: float, port: PortGeo, hysteresis: float = 1.25
) -> bool:
    """Whether a vessel previously inside ``port`` has now genuinely left.

    Departure requires the vessel to be beyond ``radius_nm * hysteresis`` so a
    position jittering across the geofence boundary does not emit a stream of
    spurious arrival/departure events.
    """
    dist = haversine_nm(lat, lon, port.latitude, port.longitude)
    return dist > port.radius_nm * hysteresis


def nearest_port(lat: float, lon: float, ports: Sequence[PortGeo]) -> Optional[tuple]:
    """Return ``(PortGeo, distance_nm)`` of the closest port, or None if empty."""
    best = None
    best_dist = None
    for port in ports:
        dist = haversine_nm(lat, lon, port.latitude, port.longitude)
        if best_dist is None or dist < best_dist:
            best = port
            best_dist = dist
    if best is None:
        return None
    return best, best_dist


def load_port_geos(basin: str = "pacific", port_type: Optional[str] = None) -> list:
    """Build the cached PortGeo list from active Port rows (ORM lives here)."""
    from .models import Port

    qs = Port.objects.filter(is_active=True, basin=basin)
    if port_type is not None:
        qs = qs.filter(port_type__in=[port_type, "both"])
    return [
        PortGeo(p.id, p.name, p.latitude, p.longitude, p.radius_nm, p.port_type)
        for p in qs
    ]
