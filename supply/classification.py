"""Vessel classification and laden/ballast detection from AIS attributes.

All thresholds are documented inline. These are deliberately simple, transparent
heuristics: the supply signal layer works off *changes versus a vessel class's
own rolling baseline*, so a modest systematic bias in absolute counts does not
distort the directional signal.
"""

from typing import Optional

# AIS ship-type codes 70-79 are the "Cargo" group (dry bulk lives here).
# Tankers (80-89) and other types are excluded.
DRY_CARGO_SHIP_TYPES = range(70, 80)

# Length bands (metres), measured as AIS dimension A + B (bow + stern offsets).
# Lower bound is exclusive of the next-smaller class; handysize floor of 150 m
# filters out most general-cargo / container feeders that also report type 70-79.
LENGTH_BANDS = [
    ("capesize", 270.0, float("inf")),
    ("panamax", 215.0, 270.0),  # includes kamsarmax
    ("supramax", 185.0, 215.0),  # includes ultramax
    ("handysize", 150.0, 185.0),
]

# Draught bands (metres), used only as a fallback when length is unknown.
DRAUGHT_BANDS = [
    ("capesize", 16.5, float("inf")),
    ("panamax", 13.5, 16.5),
    ("supramax", 12.0, 13.5),
    ("handysize", 9.0, 12.0),
]

MIN_DRY_BULK_LENGTH_M = 150.0


def is_dry_bulk_candidate(ship_type: Optional[int]) -> bool:
    """Whether an AIS ship type is in the dry-cargo group.

    Unknown (None) is treated as a candidate so vessels are kept until static
    data arrives; they classify as 'unknown' and are excluded from per-class
    aggregates until dimensions resolve.
    """
    if ship_type is None:
        return True
    return ship_type in DRY_CARGO_SHIP_TYPES


def _band_lookup(value: float, bands) -> Optional[str]:
    for name, low, high in bands:
        if low <= value < high:
            return name
    return None


def classify_vessel(length_m: Optional[float], max_draught_m: Optional[float]) -> str:
    """Classify a vessel into capesize/panamax/supramax/handysize/unknown.

    Length is the primary signal (a fixed hull dimension); draught is a fallback
    when length is missing, since draught is crew-entered and varies with cargo.
    When both are present they usually agree; on disagreement we trust length.
    Vessels shorter than 150 m (or with no usable dimension) are 'unknown'.
    """
    if length_m is not None and length_m > 0:
        if length_m < MIN_DRY_BULK_LENGTH_M:
            return "unknown"
        return _band_lookup(length_m, LENGTH_BANDS) or "unknown"

    if max_draught_m is not None and max_draught_m >= DRAUGHT_BANDS[-1][1]:
        return _band_lookup(max_draught_m, DRAUGHT_BANDS) or "unknown"

    return "unknown"


def detect_loading_condition(
    draught_m: Optional[float], max_draught_m: float, ratio: float = 0.80
) -> str:
    """Classify a vessel as laden or ballast from its reported draught.

    A vessel drawing at least ``ratio`` (default 80%) of the deepest draught we
    have ever observed for it is treated as laden, otherwise ballast.

    Returns 'unknown' when draught is missing or when we have not yet observed a
    credible loaded draught (``max_draught_m`` < 8 m), since the ratio is
    meaningless without a stable reference. Caveat: draught is manually entered
    and often stale, and ``max_draught_m`` only ratchets upward over time, so
    early-life classifications skew toward laden.
    """
    if draught_m is None or draught_m <= 0:
        return "unknown"
    if max_draught_m < 8.0:
        return "unknown"
    return "laden" if draught_m >= ratio * max_draught_m else "ballast"
