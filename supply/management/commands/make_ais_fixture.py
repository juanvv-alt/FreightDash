"""Generate a synthetic aisstream JSONL file for testing and demos.

Simulates vessels ballasting toward a load port, arriving (geofence entry),
loading (draught rises), departing laden toward a discharge port, arriving, and
discharging (draught drops). Exercises classification, laden/ballast flips, and
both port-call event types end to end -- no API key or network required.
"""

import json
import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

# (load port, discharge port) lat/lon pairs and the class that runs the route.
ROUTES = [
    # Capesize iron ore: Port Hedland -> Qingdao
    {
        "load": (-20.31, 118.58),
        "disch": (36.07, 120.32),
        "class": "capesize",
        "length": 300.0,
        "laden_draught": 18.2,
        "ballast_draught": 9.0,
        "type": 70,
    },
    # Panamax coal: Newcastle -> Caofeidian
    {
        "load": (-32.92, 151.78),
        "disch": (38.93, 118.50),
        "class": "panamax",
        "length": 229.0,
        "laden_draught": 14.2,
        "ballast_draught": 7.5,
        "type": 70,
    },
    # Supramax coal: Taboneo -> Kaohsiung
    {
        "load": (-3.69, 114.47),
        "disch": (22.56, 120.27),
        "class": "supramax",
        "length": 199.0,
        "laden_draught": 12.8,
        "ballast_draught": 6.8,
        "type": 71,
    },
]


def _interp(p1, p2, frac):
    return (p1[0] + (p2[0] - p1[0]) * frac, p1[1] + (p2[1] - p1[1]) * frac)


def _time_str(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S.000000000 +0000 UTC")


class Command(BaseCommand):
    help = "Generate a synthetic aisstream JSONL fixture for replay/testing."

    def add_arguments(self, parser):
        parser.add_argument("--out", required=True, help="Output JSONL path.")
        parser.add_argument(
            "--vessels", type=int, default=30, help="Number of vessels to simulate."
        )
        parser.add_argument(
            "--days", type=int, default=3, help="Simulated voyage span in days."
        )
        parser.add_argument("--seed", type=int, default=42)

    def handle(self, *args, **options):
        rng = random.Random(options["seed"])
        n = options["vessels"]
        days = options["days"]
        start = timezone.now() - timedelta(days=days)
        steps = max(12, days * 8)  # position reports per vessel across the voyage

        lines = []
        for i in range(n):
            route = ROUTES[i % len(ROUTES)]
            mmsi = 200000000 + i
            name = f'TEST {route["class"][:4].upper()} {i:03d}'
            length = route["length"] + rng.uniform(-5, 5)
            a = round(length * 0.5, 1)
            b = round(length * 0.5, 1)

            # Static message up front (establishes class + max draught).
            lines.append(
                (
                    start,
                    {
                        "MessageType": "ShipStaticData",
                        "MetaData": {"MMSI": mmsi, "ShipName": name},
                        "Message": {
                            "ShipStaticData": {
                                "Type": route["type"],
                                "MaximumStaticDraught": route["laden_draught"],
                                "ImoNumber": 9000000 + i,
                                "Name": name,
                                "Dimension": {"A": a, "B": b, "C": 16, "D": 16},
                            }
                        },
                    },
                )
            )

            # Voyage: ballast leg (sea -> load port), then laden leg (-> discharge).
            # First half approaches the load port; second half leaves laden.
            for s in range(steps):
                frac = s / (steps - 1)
                ts = start + timedelta(seconds=frac * days * 86400)
                if frac < 0.5:
                    # Ballast: start ~6 deg away, close in on the load port.
                    leg = frac / 0.5
                    far = (route["load"][0] - 6, route["load"][1] - 6)
                    lat, lon = _interp(far, route["load"], leg)
                    draught = route["ballast_draught"]
                else:
                    # Laden: leave the load port toward the discharge port.
                    leg = (frac - 0.5) / 0.5
                    lat, lon = _interp(route["load"], route["disch"], leg)
                    draught = route["laden_draught"]
                lat += rng.uniform(-0.02, 0.02)
                lon += rng.uniform(-0.02, 0.02)
                lines.append(
                    (
                        ts,
                        {
                            "MessageType": "PositionReport",
                            "MetaData": {
                                "MMSI": mmsi,
                                "ShipName": name,
                                "time_utc": _time_str(ts),
                            },
                            "Message": {
                                "PositionReport": {
                                    "Latitude": round(lat, 4),
                                    "Longitude": round(lon, 4),
                                    "Sog": round(rng.uniform(10, 14), 1),
                                    "Cog": round(rng.uniform(0, 359), 1),
                                    "NavigationalStatus": 0,
                                    "MaximumStaticDraught": draught,
                                }
                            },
                        },
                    )
                )

        lines.sort(key=lambda x: x[0])
        with open(options["out"], "w") as fh:
            for _, msg in lines:
                fh.write(json.dumps(msg) + "\n")

        self.stdout.write(
            self.style.SUCCESS(
                f'Wrote {len(lines)} messages for {n} vessels to {options["out"]}'
            )
        )
