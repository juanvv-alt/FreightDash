from django.db import models

ZONE_CHOICES = [
    ("NE_ASIA", "NE Asia"),
    ("SE_ASIA", "SE Asia"),
    ("AUSTRALIA", "Australia"),
    ("EAST_PACIFIC", "East Pacific"),
]

SERIES_CHOICES = [
    ("BALLAST_AT_SEA", "Ballast at Sea"),
    ("IN_PORT", "In Port"),
    ("TOTAL", "Total"),
]


class OBTonnageSnapshot(models.Model):
    """Daily Oceanbolt vessel count for one zone + series combination."""

    date = models.DateField(db_index=True)
    zone = models.CharField(max_length=20, choices=ZONE_CHOICES)
    series = models.CharField(max_length=20, choices=SERIES_CHOICES)
    vessel_count = models.PositiveIntegerField(default=0)
    vessel_dwt = models.BigIntegerField(default=0)

    class Meta:
        unique_together = [("date", "zone", "series")]
        ordering = ["-date", "zone", "series"]

    def __str__(self):
        return f"{self.date} {self.zone} {self.series}: {self.vessel_count}"


class OBForecastSignal(models.Model):
    """Computed daily directional signal per zone; persisted for history."""

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
    zone = models.CharField(max_length=20, choices=ZONE_CHOICES)
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    score = models.FloatField(help_text="Signed magnitude, roughly -3..+3")
    confidence = models.FloatField(help_text="0..1")
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    drivers = models.JSONField(default=list, blank=True)
    data_days = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [("date", "zone")]
        ordering = ["-date", "zone"]

    def __str__(self):
        return f"{self.date} {self.zone}: {self.direction} ({self.method})"


class OBUploadLog(models.Model):
    """Audit trail for CSV uploads."""

    uploaded_at = models.DateTimeField(auto_now_add=True)
    zone = models.CharField(max_length=20, choices=ZONE_CHOICES)
    series = models.CharField(max_length=20, choices=SERIES_CHOICES)
    filename = models.CharField(max_length=255)
    rows_added = models.PositiveIntegerField(default=0)
    rows_skipped = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.uploaded_at:%Y-%m-%d %H:%M} {self.zone}/{self.series} +{self.rows_added}"
