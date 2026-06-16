from django.db import models

VESSEL_CLASS_CHOICES = [
    ("capesize", "Capesize"),
    ("panamax", "Panamax"),
    ("supramax", "Supramax"),
    ("handysize", "Handysize"),
    ("unknown", "Unknown"),
]

# vessel_class values used in DailySupplySnapshot / SupplySignal: the four real
# classes above plus 'all' for the basin-wide aggregate row.
SNAPSHOT_CLASSES = ["capesize", "panamax", "supramax", "handysize"]

LOADING_CHOICES = [
    ("laden", "Laden"),
    ("ballast", "Ballast"),
    ("unknown", "Unknown"),
]


class Port(models.Model):
    """A geofenced dry-bulk load/discharge port in the basin."""

    PORT_TYPE_CHOICES = [
        ("load", "Load"),
        ("discharge", "Discharge"),
        ("both", "Both"),
    ]

    name = models.CharField(max_length=120, unique=True)
    country = models.CharField(max_length=60, blank=True)
    latitude = models.FloatField()
    longitude = models.FloatField()
    radius_nm = models.FloatField(
        default=15.0, help_text="Geofence radius in nautical miles"
    )
    port_type = models.CharField(max_length=10, choices=PORT_TYPE_CHOICES)
    basin = models.CharField(max_length=30, default="pacific")
    vessel_classes = models.JSONField(
        default=list,
        blank=True,
        help_text="Classes this port serves, e.g. ['capesize','panamax']. Empty = all.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.get_port_type_display()})"


class TrackedVessel(models.Model):
    """A dry-bulk vessel observed via AIS, with derived class particulars."""

    mmsi = models.BigIntegerField(unique=True, db_index=True)
    imo = models.BigIntegerField(null=True, blank=True)
    name = models.CharField(max_length=120, blank=True)
    ais_ship_type = models.PositiveSmallIntegerField(null=True, blank=True)
    length_m = models.FloatField(
        null=True, blank=True, help_text="AIS dimension A + B (metres)"
    )
    beam_m = models.FloatField(
        null=True, blank=True, help_text="AIS dimension C + D (metres)"
    )
    vessel_class = models.CharField(
        max_length=20, choices=VESSEL_CLASS_CHOICES, default="unknown", db_index=True
    )
    max_draught_m = models.FloatField(
        default=0.0, help_text="Maximum draught ever observed"
    )
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(db_index=True)
    is_excluded = models.BooleanField(
        default=False, help_text="Manually exclude from supply aggregates"
    )

    class Meta:
        ordering = ["name", "mmsi"]

    def __str__(self):
        label = self.name or f"MMSI {self.mmsi}"
        return f"{label} ({self.get_vessel_class_display()})"


class VesselState(models.Model):
    """Current position/state of a vessel, updated in place by the ingester."""

    vessel = models.OneToOneField(
        TrackedVessel, on_delete=models.CASCADE, related_name="state"
    )
    latitude = models.FloatField()
    longitude = models.FloatField()
    speed_knots = models.FloatField(null=True, blank=True)
    course = models.FloatField(null=True, blank=True)
    draught_m = models.FloatField(null=True, blank=True)
    nav_status = models.PositiveSmallIntegerField(null=True, blank=True)
    loading_condition = models.CharField(
        max_length=10, choices=LOADING_CHOICES, default="unknown"
    )
    current_port = models.ForeignKey(
        Port,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="vessels_in_port",
        help_text="Port whose geofence the vessel is currently inside (null = at sea)",
    )
    port_arrived_at = models.DateTimeField(null=True, blank=True)
    position_at = models.DateTimeField(
        help_text="Timestamp of the last accepted position"
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.vessel} @ ({self.latitude:.2f}, {self.longitude:.2f})"


class PortCallEvent(models.Model):
    """A vessel arrival at or departure from a port geofence."""

    EVENT_CHOICES = [
        ("arrival", "Arrival"),
        ("departure", "Departure"),
    ]

    vessel = models.ForeignKey(
        TrackedVessel, on_delete=models.CASCADE, related_name="port_calls"
    )
    port = models.ForeignKey(Port, on_delete=models.CASCADE, related_name="calls")
    event_type = models.CharField(max_length=10, choices=EVENT_CHOICES)
    timestamp = models.DateTimeField(db_index=True)
    draught_m = models.FloatField(null=True, blank=True)
    loading_condition = models.CharField(
        max_length=10, choices=LOADING_CHOICES, default="unknown"
    )

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["port", "timestamp"]),
            models.Index(fields=["vessel", "timestamp"]),
        ]

    def __str__(self):
        return f"{self.vessel} {self.event_type} {self.port} @ {self.timestamp:%Y-%m-%d %H:%M}"


class DailySupplySnapshot(models.Model):
    """Daily aggregate of vessel supply per class (+ an 'all' row) and basin."""

    date = models.DateField(db_index=True)
    vessel_class = models.CharField(max_length=20, db_index=True)
    basin = models.CharField(max_length=30, default="pacific")

    in_port_load_count = models.PositiveIntegerField(default=0)
    in_port_discharge_count = models.PositiveIntegerField(default=0)
    ballast_at_sea_count = models.PositiveIntegerField(default=0)
    laden_at_sea_count = models.PositiveIntegerField(default=0)
    expected_open_7d = models.PositiveIntegerField(default=0)
    expected_open_14d = models.PositiveIntegerField(default=0)
    total_tracked = models.PositiveIntegerField(
        default=0, help_text="Fresh vessels (seen < staleness window) in basin"
    )

    arrivals_load_24h = models.PositiveIntegerField(default=0)
    departures_load_24h = models.PositiveIntegerField(default=0)
    arrivals_discharge_24h = models.PositiveIntegerField(default=0)
    departures_discharge_24h = models.PositiveIntegerField(default=0)

    avg_speed_laden = models.FloatField(null=True, blank=True)
    avg_speed_ballast = models.FloatField(null=True, blank=True)

    class Meta:
        unique_together = [("date", "vessel_class", "basin")]
        ordering = ["-date", "vessel_class"]

    def __str__(self):
        return f"{self.date} {self.vessel_class} ({self.basin})"


class SupplySignal(models.Model):
    """Computed daily directional signal per class; kept for backtesting."""

    DIRECTION_CHOICES = [
        ("bullish", "Bullish"),
        ("bearish", "Bearish"),
        ("neutral", "Neutral"),
    ]
    METHOD_CHOICES = [
        ("regression", "Regression"),
        ("zscore", "Z-score heuristic"),
        ("snapshot", "Snapshot ratio (cold start)"),
        ("insufficient", "Insufficient data"),
    ]

    date = models.DateField(db_index=True)
    vessel_class = models.CharField(max_length=20)
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    score = models.FloatField(help_text="Signed magnitude, roughly -3..+3")
    confidence = models.FloatField(help_text="0..1")
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    drivers = models.JSONField(
        default=list, blank=True, help_text="Plain-English driver strings"
    )
    data_days = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [("date", "vessel_class")]
        ordering = ["-date", "vessel_class"]

    def __str__(self):
        return f"{self.date} {self.vessel_class}: {self.direction} ({self.method})"
