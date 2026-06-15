"""AIS ingestion engine for aisstream.io.

Design goals:
- **No per-message storage.** Every AIS message updates a small in-memory cache;
  a DB write happens only on a *meaningful* change (moved far enough, draught
  changed, port geofence crossed, or a max staleness interval elapsed).
- **One code path for live and replay.** The websocket loop and the offline
  ``replay()`` helper both funnel through ``process_message``, so tests and
  keyless demos exercise exactly the production logic.
- **Sync ORM, async transport.** The websocket client is async; DB work is plain
  synchronous ORM bridged with ``asgiref.sync.sync_to_async``.

aisstream.io message shape (the fields we use)::

    {"MessageType": "PositionReport",
     "MetaData": {"MMSI": 1, "ShipName": "X", "time_utc": "2024-... UTC"},
     "Message": {"PositionReport": {"Latitude": .., "Longitude": ..,
                                    "Sog": .., "Cog": .., "NavigationalStatus": ..}}}
    {"MessageType": "ShipStaticData",
     "MetaData": {"MMSI": 1},
     "Message": {"ShipStaticData": {"Type": 70, "MaximumStaticDraught": 14.2,
                                    "ImoNumber": 9, "Name": "X",
                                    "Dimension": {"A":100,"B":120,"C":15,"D":15}}}}
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Optional

from django.db import transaction
from django.utils import timezone

from .classification import (classify_vessel, detect_loading_condition,
                             is_dry_bulk_candidate)
from .geo import PortGeo, find_containing_port, haversine_nm, is_departed

logger = logging.getLogger(__name__)

AISSTREAM_URL = "wss://stream.aisstream.io/v0/stream"

# Two boxes covering the Pacific dry-bulk basin. aisstream bounding boxes are
# [[lat1, lon1], [lat2, lon2]] (corner pairs).
PACIFIC_BOUNDING_BOXES = [
    [[-45.0, 90.0], [15.0, 160.0]],  # Indonesia / Australia / SE Asia
    [[15.0, 105.0], [48.0, 150.0]],  # China / Japan / Korea / Taiwan
]


@dataclass
class CachedVessel:
    """Hot in-memory state for one vessel; avoids a DB read per message."""

    mmsi: int
    lat: Optional[float] = None
    lon: Optional[float] = None
    draught_m: Optional[float] = None
    max_draught_m: float = 0.0
    length_m: Optional[float] = None
    beam_m: Optional[float] = None
    ship_type: Optional[int] = None
    name: str = ""
    imo: Optional[int] = None
    vessel_class: str = "unknown"
    current_port_id: Optional[int] = None
    last_write_lat: Optional[float] = None
    last_write_lon: Optional[float] = None
    last_write_draught: Optional[float] = None
    last_write_at: Optional[datetime] = None
    static_dirty: bool = False


@dataclass
class IngestStats:
    messages: int = 0
    position_messages: int = 0
    static_messages: int = 0
    state_writes: int = 0
    arrivals: int = 0
    departures: int = 0
    skipped_non_bulk: int = 0
    vessels: set = field(default_factory=set)

    def as_dict(self) -> dict:
        return {
            "messages": self.messages,
            "position_messages": self.position_messages,
            "static_messages": self.static_messages,
            "state_writes": self.state_writes,
            "arrivals": self.arrivals,
            "departures": self.departures,
            "skipped_non_bulk": self.skipped_non_bulk,
            "vessels": len(self.vessels),
        }


def _parse_ais_time(value, default=None) -> datetime:
    """Parse aisstream's ``time_utc`` ('2024-01-02 03:04:05.000 +0000 UTC')."""
    if not value:
        return default or timezone.now()
    cleaned = str(value).replace(" UTC", "").strip()
    # Trim fractional seconds to 6 digits (Python can't parse 9-digit nanos).
    for fmt in ("%Y-%m-%d %H:%M:%S.%f %z", "%Y-%m-%d %H:%M:%S %z"):
        try:
            return datetime.strptime(_truncate_fractional(cleaned), fmt)
        except ValueError:
            continue
    return default or timezone.now()


def _truncate_fractional(value: str) -> str:
    if "." not in value:
        return value
    head, rest = value.split(".", 1)
    digits = ""
    for ch in rest:
        if ch.isdigit():
            digits += ch
        else:
            rest_tail = rest[len(digits) :]
            return f"{head}.{digits[:6]}{rest_tail}"
    return f"{head}.{digits[:6]}"


class AISIngestor:
    """Consume AIS messages, maintain vessel state, emit port-call events."""

    def __init__(
        self,
        api_key: str,
        ports: list,
        *,
        min_move_nm: float = 5.0,
        min_draught_delta: float = 0.3,
        max_write_interval_s: int = 1800,
        stdout=None,
    ):
        self.api_key = api_key
        self.ports: list[PortGeo] = list(ports)
        self.ports_by_id = {p.id: p for p in self.ports}
        self.min_move_nm = min_move_nm
        self.min_draught_delta = min_draught_delta
        self.max_write_interval_s = max_write_interval_s
        self.stdout = stdout
        self.cache: dict[int, CachedVessel] = {}
        self.stats = IngestStats()
        self._stop = False

    # ----- message dispatch -------------------------------------------------

    def process_message(self, msg: dict) -> None:
        """Route one parsed AIS message (sync; safe to call from replay)."""
        self.stats.messages += 1
        msg_type = msg.get("MessageType")
        meta = msg.get("MetaData") or {}
        body = (msg.get("Message") or {}).get(msg_type) or {}
        if msg_type == "ShipStaticData":
            self.stats.static_messages += 1
            self._handle_static(meta, body)
        elif msg_type == "PositionReport":
            self.stats.position_messages += 1
            self._handle_position(meta, body)
        else:
            # Log unexpected types — catches auth errors / API responses from aisstream.io
            logger.warning("AIS unhandled message type %r: %s", msg_type, str(msg)[:300])

    def _cached(self, mmsi: int) -> CachedVessel:
        cv = self.cache.get(mmsi)
        if cv is None:
            cv = CachedVessel(mmsi=mmsi)
            self.cache[mmsi] = cv
        return cv

    def _handle_static(self, meta: dict, body: dict) -> None:
        mmsi = meta.get("MMSI") or body.get("UserID")
        if mmsi is None:
            return
        mmsi = int(mmsi)
        ship_type = body.get("Type")
        if not is_dry_bulk_candidate(ship_type):
            self.stats.skipped_non_bulk += 1
            self.cache.pop(mmsi, None)
            return

        cv = self._cached(mmsi)
        cv.ship_type = ship_type if ship_type is not None else cv.ship_type
        dim = body.get("Dimension") or {}
        a, b = dim.get("A"), dim.get("B")
        c, d = dim.get("C"), dim.get("D")
        if a is not None and b is not None:
            cv.length_m = float(a) + float(b)
        if c is not None and d is not None:
            cv.beam_m = float(c) + float(d)
        name = body.get("Name") or meta.get("ShipName")
        if name:
            cv.name = name.strip()
        imo = body.get("ImoNumber")
        if imo:
            cv.imo = int(imo)
        draught = body.get("MaximumStaticDraught")
        if draught:
            cv.max_draught_m = max(cv.max_draught_m, float(draught))
        cv.vessel_class = classify_vessel(cv.length_m, cv.max_draught_m)
        cv.static_dirty = True
        self._write_static(cv, meta)

    def _handle_position(self, meta: dict, body: dict) -> None:
        mmsi = meta.get("MMSI") or body.get("UserID")
        if mmsi is None:
            return
        mmsi = int(mmsi)
        lat = body.get("Latitude", meta.get("latitude"))
        lon = body.get("Longitude", meta.get("longitude"))
        if lat is None or lon is None:
            return
        lat, lon = float(lat), float(lon)
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return

        cv = self._cached(mmsi)
        ts = _parse_ais_time(meta.get("time_utc"))
        sog = body.get("Sog")
        cog = body.get("Cog")
        nav = body.get("NavigationalStatus")
        draught = body.get("MaximumStaticDraught")  # rarely present on position
        if draught:
            cv.draught_m = float(draught)
            cv.max_draught_m = max(cv.max_draught_m, cv.draught_m)
        name = meta.get("ShipName")
        if name and not cv.name:
            cv.name = name.strip()

        port_event = self._resolve_port_transition(cv, lat, lon, ts)
        should_write = self._should_write(cv, lat, lon) or port_event is not None
        cv.lat, cv.lon = lat, lon

        if should_write:
            self._write_position(cv, lat, lon, ts, sog, cog, nav, port_event)

    # ----- write decisions --------------------------------------------------

    def _should_write(self, cv: CachedVessel, lat: float, lon: float) -> bool:
        if cv.last_write_at is None:
            return True
        now = timezone.now()
        if (now - cv.last_write_at).total_seconds() >= self.max_write_interval_s:
            return True
        if cv.last_write_lat is not None:
            moved = haversine_nm(cv.last_write_lat, cv.last_write_lon, lat, lon)
            if moved >= self.min_move_nm:
                return True
        if cv.draught_m is not None and cv.last_write_draught is not None:
            if abs(cv.draught_m - cv.last_write_draught) >= self.min_draught_delta:
                return True
        if cv.draught_m is not None and cv.last_write_draught is None:
            return True
        return False

    def _resolve_port_transition(self, cv, lat, lon, ts) -> Optional[tuple]:
        """Return ('arrival'|'departure', port_id) if the geofence state flips."""
        prev_port = (
            self.ports_by_id.get(cv.current_port_id)
            if cv.current_port_id is not None
            else None
        )
        if prev_port is not None:
            if is_departed(lat, lon, prev_port):
                cv.current_port_id = None
                # Re-check whether the new position is already inside another port.
                entered = find_containing_port(lat, lon, self.ports)
                if entered is not None:
                    cv.current_port_id = entered.id
                    return ("arrival", entered.id)
                return ("departure", prev_port.id)
            return None  # still inside same fence (hysteresis not exceeded)

        entered = find_containing_port(lat, lon, self.ports)
        if entered is not None:
            cv.current_port_id = entered.id
            return ("arrival", entered.id)
        return None

    # ----- persistence ------------------------------------------------------

    @transaction.atomic
    def _write_static(self, cv: CachedVessel, meta: dict) -> None:
        from .models import TrackedVessel

        now = timezone.now()
        vessel, _ = TrackedVessel.objects.update_or_create(
            mmsi=cv.mmsi,
            defaults={
                "name": cv.name,
                "imo": cv.imo,
                "ais_ship_type": cv.ship_type,
                "length_m": cv.length_m,
                "beam_m": cv.beam_m,
                "vessel_class": cv.vessel_class,
                "last_seen": now,
            },
        )
        if cv.max_draught_m > vessel.max_draught_m:
            vessel.max_draught_m = cv.max_draught_m
            vessel.save(update_fields=["max_draught_m"])
        cv.static_dirty = False
        self.stats.vessels.add(cv.mmsi)

    @transaction.atomic
    def _write_position(self, cv, lat, lon, ts, sog, cog, nav, port_event) -> None:
        from .models import PortCallEvent, TrackedVessel, VesselState

        vessel, _ = TrackedVessel.objects.get_or_create(
            mmsi=cv.mmsi,
            defaults={
                "name": cv.name,
                "imo": cv.imo,
                "ais_ship_type": cv.ship_type,
                "length_m": cv.length_m,
                "beam_m": cv.beam_m,
                "vessel_class": cv.vessel_class,
                "max_draught_m": cv.max_draught_m,
                "last_seen": ts,
            },
        )
        if vessel.max_draught_m > cv.max_draught_m:
            cv.max_draught_m = vessel.max_draught_m
            cv.vessel_class = classify_vessel(cv.length_m, cv.max_draught_m)

        loading = detect_loading_condition(cv.draught_m, cv.max_draught_m)
        port_id = cv.current_port_id
        arrived_at = ts if (port_event and port_event[0] == "arrival") else None

        state_defaults = {
            "latitude": lat,
            "longitude": lon,
            "speed_knots": float(sog) if sog is not None else None,
            "course": float(cog) if cog is not None else None,
            "draught_m": cv.draught_m,
            "nav_status": nav,
            "loading_condition": loading,
            "current_port_id": port_id,
            "position_at": ts,
        }
        existing = VesselState.objects.filter(vessel=vessel).first()
        if existing is not None and arrived_at is None and port_id is not None:
            state_defaults["port_arrived_at"] = existing.port_arrived_at
        else:
            state_defaults["port_arrived_at"] = arrived_at
        VesselState.objects.update_or_create(vessel=vessel, defaults=state_defaults)

        if vessel.last_seen is None or ts > vessel.last_seen:
            vessel.last_seen = ts
            vessel.save(update_fields=["last_seen"])

        if port_event is not None:
            event_type, ev_port_id = port_event
            PortCallEvent.objects.create(
                vessel=vessel,
                port_id=ev_port_id,
                event_type=event_type,
                timestamp=ts,
                draught_m=cv.draught_m,
                loading_condition=loading,
            )
            if event_type == "arrival":
                self.stats.arrivals += 1
            else:
                self.stats.departures += 1

        cv.last_write_lat = lat
        cv.last_write_lon = lon
        cv.last_write_draught = cv.draught_m
        cv.last_write_at = timezone.now()
        self.stats.state_writes += 1
        self.stats.vessels.add(cv.mmsi)

    # ----- entry points -----------------------------------------------------

    def replay(self, lines: Iterable[str]) -> dict:
        """Feed JSON-per-line AIS messages synchronously. Returns stat counts."""
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            self.process_message(msg)
        return self.stats.as_dict()

    async def run(self, duration_seconds: int = 0) -> None:
        """Connect to aisstream and ingest until stopped or duration elapses."""
        import websockets
        from asgiref.sync import sync_to_async

        deadline = None
        if duration_seconds and duration_seconds > 0:
            deadline = timezone.now().timestamp() + duration_seconds

        backoff = 5
        subscribe = {
            "APIKey": self.api_key,
            "BoundingBoxes": PACIFIC_BOUNDING_BOXES,
            "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
        }
        # thread_sensitive=False: safe for WSGI daemon threads; each call gets its
        # own thread-pool thread with its own Django DB connection.
        process = sync_to_async(self.process_message, thread_sensitive=False)

        while not self._stop:
            if deadline and timezone.now().timestamp() >= deadline:
                self._log_stats()
                return
            try:
                async with websockets.connect(AISSTREAM_URL, ping_interval=20) as ws:
                    await ws.send(json.dumps(subscribe))
                    self._log(
                        f"Connected to aisstream; subscribed to {len(PACIFIC_BOUNDING_BOXES)} boxes."
                    )
                    backoff = 5
                    async for raw in ws:
                        if deadline and timezone.now().timestamp() >= deadline:
                            self._log_stats()
                            return
                        try:
                            msg = json.loads(raw)
                        except (json.JSONDecodeError, TypeError):
                            continue
                        await process(msg)
                        if self._stop:
                            self._log_stats()
                            return
            except asyncio.CancelledError:
                self._log_stats()
                raise
            except Exception as exc:  # reconnect on any transport error
                self._log(f"AIS stream error: {exc!r}; reconnecting in {backoff}s")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 300)
        self._log_stats()

    def stop(self) -> None:
        self._stop = True

    def _log(self, message: str) -> None:
        if self.stdout is not None:
            self.stdout.write(message)
        logger.warning(message)

    def _log_stats(self) -> None:
        stats = self.stats.as_dict()
        msg = (
            f"AIS ingest session complete — "
            f"{stats['messages']} messages received "
            f"({stats['position_messages']} positions, {stats['static_messages']} static, "
            f"{stats['skipped_non_bulk']} skipped non-bulk), "
            f"{stats['vessels']} vessels, {stats['state_writes']} DB writes, "
            f"{stats['arrivals']} arrivals, {stats['departures']} departures"
        )
        self._log(msg)
        try:
            from django.core.cache import cache
            cache.set("ais_last_stats", stats, timeout=86400)
            cache.set("ais_last_stats_time", timezone.now().isoformat(), timeout=86400)
        except Exception:
            pass
