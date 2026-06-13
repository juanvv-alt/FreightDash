from django.core.management.base import BaseCommand

from supply.models import Port

# Approximate coordinates (to ~0.05 deg, fine at these geofence radii) for major
# Pacific dry-bulk ports. Anchorage-loading ports (Indonesian coal, large Chinese
# discharge complexes) use a wider radius to capture vessels queued offshore --
# that queue is exactly where the supply signal lives.
PACIFIC_PORTS = [
    # --- Australia: iron ore loading (capesize) ---
    {
        "name": "Port Hedland",
        "country": "Australia",
        "latitude": -20.31,
        "longitude": 118.58,
        "radius_nm": 20,
        "port_type": "load",
        "vessel_classes": ["capesize"],
    },
    {
        "name": "Dampier",
        "country": "Australia",
        "latitude": -20.66,
        "longitude": 116.71,
        "radius_nm": 18,
        "port_type": "load",
        "vessel_classes": ["capesize"],
    },
    {
        "name": "Port Walcott",
        "country": "Australia",
        "latitude": -20.59,
        "longitude": 117.19,
        "radius_nm": 15,
        "port_type": "load",
        "vessel_classes": ["capesize"],
    },
    # --- Australia: coal loading (capesize / panamax) ---
    {
        "name": "Newcastle",
        "country": "Australia",
        "latitude": -32.92,
        "longitude": 151.78,
        "radius_nm": 18,
        "port_type": "load",
        "vessel_classes": ["capesize", "panamax"],
    },
    {
        "name": "Hay Point",
        "country": "Australia",
        "latitude": -21.27,
        "longitude": 149.30,
        "radius_nm": 18,
        "port_type": "load",
        "vessel_classes": ["capesize", "panamax"],
    },
    {
        "name": "Gladstone",
        "country": "Australia",
        "latitude": -23.83,
        "longitude": 151.25,
        "radius_nm": 15,
        "port_type": "load",
        "vessel_classes": ["capesize", "panamax"],
    },
    {
        "name": "Abbot Point",
        "country": "Australia",
        "latitude": -19.88,
        "longitude": 148.08,
        "radius_nm": 15,
        "port_type": "load",
        "vessel_classes": ["capesize", "panamax"],
    },
    {
        "name": "Port Kembla",
        "country": "Australia",
        "latitude": -34.46,
        "longitude": 150.90,
        "radius_nm": 12,
        "port_type": "load",
        "vessel_classes": ["panamax"],
    },
    # --- Indonesia: coal loading (anchorage; wide radius) ---
    {
        "name": "Samarinda",
        "country": "Indonesia",
        "latitude": -0.55,
        "longitude": 117.27,
        "radius_nm": 25,
        "port_type": "load",
        "vessel_classes": ["panamax", "supramax"],
    },
    {
        "name": "Taboneo",
        "country": "Indonesia",
        "latitude": -3.69,
        "longitude": 114.47,
        "radius_nm": 25,
        "port_type": "load",
        "vessel_classes": ["panamax", "supramax"],
    },
    {
        "name": "Balikpapan",
        "country": "Indonesia",
        "latitude": -1.27,
        "longitude": 116.81,
        "radius_nm": 22,
        "port_type": "load",
        "vessel_classes": ["panamax", "supramax"],
    },
    {
        "name": "Tarahan",
        "country": "Indonesia",
        "latitude": -5.55,
        "longitude": 105.32,
        "radius_nm": 20,
        "port_type": "load",
        "vessel_classes": ["panamax", "supramax"],
    },
    {
        "name": "Muara Berau",
        "country": "Indonesia",
        "latitude": -0.28,
        "longitude": 117.62,
        "radius_nm": 25,
        "port_type": "load",
        "vessel_classes": ["panamax", "supramax"],
    },
    # --- China: discharge ---
    {
        "name": "Qingdao",
        "country": "China",
        "latitude": 36.07,
        "longitude": 120.32,
        "radius_nm": 20,
        "port_type": "discharge",
        "vessel_classes": ["capesize", "panamax"],
    },
    {
        "name": "Caofeidian",
        "country": "China",
        "latitude": 38.93,
        "longitude": 118.50,
        "radius_nm": 20,
        "port_type": "discharge",
        "vessel_classes": ["capesize", "panamax"],
    },
    {
        "name": "Jingtang",
        "country": "China",
        "latitude": 39.21,
        "longitude": 119.01,
        "radius_nm": 18,
        "port_type": "discharge",
        "vessel_classes": ["capesize", "panamax"],
    },
    {
        "name": "Rizhao",
        "country": "China",
        "latitude": 35.39,
        "longitude": 119.55,
        "radius_nm": 18,
        "port_type": "discharge",
        "vessel_classes": ["capesize", "panamax"],
    },
    {
        "name": "Ningbo-Zhoushan",
        "country": "China",
        "latitude": 29.94,
        "longitude": 121.85,
        "radius_nm": 25,
        "port_type": "discharge",
        "vessel_classes": ["capesize", "panamax"],
    },
    {
        "name": "Bayuquan",
        "country": "China",
        "latitude": 40.27,
        "longitude": 122.10,
        "radius_nm": 15,
        "port_type": "discharge",
        "vessel_classes": ["panamax", "supramax"],
    },
    {
        "name": "Fangcheng",
        "country": "China",
        "latitude": 21.60,
        "longitude": 108.36,
        "radius_nm": 15,
        "port_type": "discharge",
        "vessel_classes": ["panamax", "supramax"],
    },
    {
        "name": "Zhanjiang",
        "country": "China",
        "latitude": 21.18,
        "longitude": 110.42,
        "radius_nm": 15,
        "port_type": "discharge",
        "vessel_classes": ["capesize", "panamax"],
    },
    {
        "name": "Lianyungang",
        "country": "China",
        "latitude": 34.74,
        "longitude": 119.45,
        "radius_nm": 15,
        "port_type": "discharge",
        "vessel_classes": ["panamax", "supramax"],
    },
    {
        "name": "Nansha",
        "country": "China",
        "latitude": 22.76,
        "longitude": 113.60,
        "radius_nm": 15,
        "port_type": "discharge",
        "vessel_classes": ["panamax", "supramax"],
    },
    # --- Japan: discharge ---
    {
        "name": "Kashima",
        "country": "Japan",
        "latitude": 35.93,
        "longitude": 140.69,
        "radius_nm": 15,
        "port_type": "discharge",
        "vessel_classes": ["capesize", "panamax"],
    },
    {
        "name": "Oita",
        "country": "Japan",
        "latitude": 33.26,
        "longitude": 131.69,
        "radius_nm": 12,
        "port_type": "discharge",
        "vessel_classes": ["capesize", "panamax"],
    },
    {
        "name": "Mizushima",
        "country": "Japan",
        "latitude": 34.50,
        "longitude": 133.74,
        "radius_nm": 12,
        "port_type": "discharge",
        "vessel_classes": ["panamax", "supramax"],
    },
    {
        "name": "Kisarazu",
        "country": "Japan",
        "latitude": 35.37,
        "longitude": 139.87,
        "radius_nm": 15,
        "port_type": "discharge",
        "vessel_classes": ["capesize", "panamax"],
    },
    # --- Korea: discharge ---
    {
        "name": "Gwangyang",
        "country": "South Korea",
        "latitude": 34.90,
        "longitude": 127.74,
        "radius_nm": 15,
        "port_type": "discharge",
        "vessel_classes": ["capesize", "panamax"],
    },
    {
        "name": "Pohang",
        "country": "South Korea",
        "latitude": 36.05,
        "longitude": 129.38,
        "radius_nm": 12,
        "port_type": "discharge",
        "vessel_classes": ["capesize", "panamax"],
    },
    {
        "name": "Dangjin",
        "country": "South Korea",
        "latitude": 37.00,
        "longitude": 126.75,
        "radius_nm": 15,
        "port_type": "discharge",
        "vessel_classes": ["capesize", "panamax"],
    },
    # --- Taiwan: discharge ---
    {
        "name": "Kaohsiung",
        "country": "Taiwan",
        "latitude": 22.56,
        "longitude": 120.27,
        "radius_nm": 12,
        "port_type": "discharge",
        "vessel_classes": ["panamax", "supramax"],
    },
    {
        "name": "Taichung",
        "country": "Taiwan",
        "latitude": 24.27,
        "longitude": 120.51,
        "radius_nm": 12,
        "port_type": "discharge",
        "vessel_classes": ["capesize", "panamax"],
    },
    # --- Hub / orders waypoint ---
    {
        "name": "Singapore",
        "country": "Singapore",
        "latitude": 1.22,
        "longitude": 103.85,
        "radius_nm": 25,
        "port_type": "both",
        "vessel_classes": [],
    },
]


class Command(BaseCommand):
    help = "Seed major Pacific dry-bulk load/discharge ports for AIS geofencing."

    def handle(self, *args, **options):
        created = 0
        updated = 0
        for data in PACIFIC_PORTS:
            obj, was_created = Port.objects.update_or_create(
                name=data["name"],
                defaults={**data, "basin": "pacific", "is_active": True},
            )
            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f"Created port: {obj.name}"))
            else:
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Pacific ports seeded: {created} created, {updated} updated "
                f"({Port.objects.count()} total)."
            )
        )
