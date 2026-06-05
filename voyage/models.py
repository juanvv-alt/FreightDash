from django.db import models


VESSEL_SIZE_CHOICES = [
    ('capesize', 'Capesize'),
    ('panamax', 'Panamax'),
    ('supramax', 'Supramax'),
    ('handysize', 'Handysize'),
    ('bunker', 'Bunker'),
]


class RouteParameters(models.Model):
    """
    Stores voyage parameters for different shipping routes.
    Used to calculate TCE (Time Charter Equivalent).
    """
    route = models.CharField(max_length=255, unique=True)
    
    # Distance parameters
    ballast_distance = models.FloatField(default=3496, help_text="Nautical miles")
    laden_distance = models.FloatField(default=3494, help_text="Nautical miles")
    
    # Cargo parameters
    intake = models.FloatField(default=173500, help_text="Metric tons")
    load_rate = models.FloatField(default=90000, help_text="MT per day")
    discharge_rate = models.FloatField(default=30000, help_text="MT per day")
    turntime_hours = models.FloatField(default=30, help_text="Hours")
    
    # Port expenses
    port_exp_load_port = models.FloatField(default=145000, help_text="Currency units")
    port_exp_discharge_port = models.FloatField(default=120000, help_text="Currency units")
    
    # Commission and margins
    freight_commission_pct = models.FloatField(default=5, help_text="Percentage")
    sea_margin_pct = models.FloatField(default=7, help_text="Percentage")
    
    # Speed parameters
    ballast_speed = models.FloatField(default=13, help_text="Nautical miles per hour")
    laden_speed = models.FloatField(default=12, help_text="Nautical miles per hour")
    
    # Consumption parameters
    ballast_consumption = models.FloatField(default=43, help_text="MT per 24 hours")
    laden_consumption = models.FloatField(default=43, help_text="MT per 24 hours")
    port_consumption = models.FloatField(default=7.5, help_text="MT per 24 hours")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['route']
        verbose_name_plural = "Route Parameters"

    def __str__(self):
        return self.route


class CustomIndexPreset(models.Model):
    """User-defined index combinations across vessel classes."""

    name = models.CharField(max_length=100, unique=True)
    indices = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Custom Index Preset'
        verbose_name_plural = 'Custom Index Presets'

    def __str__(self):
        return self.name


class AvailableIndex(models.Model):
    """Configurable list of index columns available in the UI and uploads."""

    name = models.CharField(max_length=120, unique=True)
    vessel_size = models.CharField(max_length=20, choices=VESSEL_SIZE_CHOICES)
    order = models.PositiveIntegerField(default=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['vessel_size', 'order', 'name']
        verbose_name = 'Available Index'
        verbose_name_plural = 'Available Indices'

    def __str__(self):
        return self.name


class DailyIndexValue(models.Model):
    """Daily value of an index uploaded from preset spreadsheet format."""

    index = models.ForeignKey(AvailableIndex, on_delete=models.CASCADE, related_name='daily_values')
    date = models.DateField()
    value = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', 'index__name']
        unique_together = [('index', 'date')]
        verbose_name = 'Daily Index Value'
        verbose_name_plural = 'Daily Index Values'

    def __str__(self):
        return f"{self.index.name} {self.date}: {self.value}"


class VesselProfile(models.Model):
    """Vessel static technical particulars for matrix calculations."""

    name = models.CharField(max_length=120, unique=True)
    vessel_size = models.CharField(max_length=20, choices=VESSEL_SIZE_CHOICES, default='panamax')
    dwt = models.FloatField(help_text='Deadweight in metric tons')
    draft = models.FloatField(help_text='Design draft in meters')
    npc = models.FloatField(default=0, help_text='Non-performance claims or daily fixed cost, optional')
    grain_capacity = models.FloatField(help_text='Grain capacity in cubic meters')
    default_port_consumption = models.FloatField(default=3.0, help_text='MT/day in port if profile does not override')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Vessel Profile'
        verbose_name_plural = 'Vessel Parameters'

    def __str__(self):
        return self.name


class VesselSpeedProfile(models.Model):
    """Speed profile variants, e.g. CP, ECO, SUPER ECO."""

    vessel = models.ForeignKey(VesselProfile, on_delete=models.CASCADE, related_name='speed_profiles')
    name = models.CharField(max_length=60, help_text='e.g. CP, ECO, SUPER ECO')
    ballast_speed = models.FloatField(help_text='Knots')
    laden_speed = models.FloatField(help_text='Knots')
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['vessel__name', 'name']
        unique_together = [('vessel', 'name')]
        verbose_name = 'Vessel Speed Profile'
        verbose_name_plural = 'Vessel Speed Profiles'

    def __str__(self):
        return f"{self.vessel.name} - {self.name}"


class VesselFuelProfile(models.Model):
    """Consumption profile variants with one or more fuel lines."""

    vessel = models.ForeignKey(VesselProfile, on_delete=models.CASCADE, related_name='fuel_profiles')
    name = models.CharField(max_length=60, help_text='e.g. CP CONS, ECO CONS')
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['vessel__name', 'name']
        unique_together = [('vessel', 'name')]
        verbose_name = 'Vessel Fuel Profile'
        verbose_name_plural = 'Vessel Fuel Profiles'

    def __str__(self):
        return f"{self.vessel.name} - {self.name}"


class VesselFuelConsumption(models.Model):
    """Per-fuel daily consumption values for sea and port."""

    fuel_profile = models.ForeignKey(VesselFuelProfile, on_delete=models.CASCADE, related_name='fuel_lines')
    fuel_type = models.CharField(max_length=60, help_text='e.g. VLSFO, LSFO, MGO')
    sea_consumption = models.FloatField(default=0, help_text='MT/day at sea')
    port_consumption = models.FloatField(default=0, help_text='MT/day in port')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['fuel_profile__vessel__name', 'fuel_profile__name', 'fuel_type']
        unique_together = [('fuel_profile', 'fuel_type')]
        verbose_name = 'Vessel Fuel Consumption Line'
        verbose_name_plural = 'Vessel Fuel Consumption Lines'

    def __str__(self):
        return f"{self.fuel_profile} - {self.fuel_type}"


class FreightVoyage(models.Model):
    """Voyage assumptions used to build freight-rate matrix columns."""

    INTAKE_MODE_CHOICES = [
        ('manual', 'Manual'),
        ('calculated', 'Calculated from vessel, draft and stowage'),
    ]

    name = models.CharField(max_length=160, unique=True)
    commodity = models.CharField(max_length=80, blank=True)
    load_ports = models.JSONField(default=list, help_text='One or many load port names')
    discharge_ports = models.JSONField(default=list, help_text='One or many discharge port names')
    ballast_port = models.CharField(max_length=120)
    load_rate = models.FloatField(help_text='MT/day')
    discharge_rate = models.FloatField(help_text='MT/day')
    turntime_load_hours = models.FloatField(default=12)
    turntime_discharge_hours = models.FloatField(default=12)
    port_exp_load_port = models.FloatField(default=0)
    port_exp_discharge_port = models.FloatField(default=0)
    misc_expenses = models.FloatField(default=0)

    vessel = models.ForeignKey(VesselProfile, on_delete=models.PROTECT, related_name='voyages')
    speed_profile = models.ForeignKey(
        VesselSpeedProfile,
        on_delete=models.PROTECT,
        related_name='voyages',
        null=True,
        blank=True,
    )
    fuel_profile = models.ForeignKey(
        VesselFuelProfile,
        on_delete=models.PROTECT,
        related_name='voyages',
        null=True,
        blank=True,
    )

    intake_mode = models.CharField(max_length=20, choices=INTAKE_MODE_CHOICES, default='manual')
    intake_manual = models.FloatField(default=0, help_text='MT if manual mode')
    draft_limit = models.FloatField(default=0, help_text='Optional limiting draft in meters')
    stowage_factor = models.FloatField(default=0, help_text='cbm/mt used for intake calc mode')

    apply_same_sea_margin = models.BooleanField(default=True)
    sea_margin_ballast_pct = models.FloatField(default=7)
    sea_margin_laden_pct = models.FloatField(default=7)
    ballast_distance = models.FloatField(help_text='NM total ballast leg')
    laden_distance = models.FloatField(help_text='NM total laden leg')

    address_commission_pct = models.FloatField(default=0)
    brokerage_commission_pct = models.FloatField(default=0)
    daily_hire_index = models.ForeignKey(
        AvailableIndex,
        on_delete=models.PROTECT,
        related_name='hire_voyages',
        null=True,
        blank=True,
        help_text='Index whose daily value is target TCE for this voyage',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Freight Voyage'
        verbose_name_plural = 'Voyage Parameters'

    def __str__(self):
        return self.name


class VoyageFuelSplit(models.Model):
    """Fuel index basket used to price total voyage fuel cost."""

    voyage = models.ForeignKey(FreightVoyage, on_delete=models.CASCADE, related_name='fuel_splits')
    fuel_index = models.ForeignKey(AvailableIndex, on_delete=models.PROTECT, related_name='fuel_split_lines')
    weight_pct = models.FloatField(default=100, help_text='Weight in percentage points')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['voyage__name', 'fuel_index__name']
        unique_together = [('voyage', 'fuel_index')]
        verbose_name = 'Voyage Fuel Split'
        verbose_name_plural = 'Voyage Fuel Splits'

    def __str__(self):
        return f"{self.voyage.name} - {self.fuel_index.name} ({self.weight_pct}%)"


class VesselCompareConfig(models.Model):
    """Singleton storing market inputs and voyage parameters for the vessel comparison tool."""
    hire = models.FloatField(default=23000)
    ifo_price = models.FloatField(default=800)
    mgo_price = models.FloatField(default=1300)
    weather_factor = models.FloatField(default=1.07)

    v1_name = models.CharField(max_length=160, default='Abbot Point to VN')
    v1_ballast_dist = models.FloatField(default=3734)
    v1_laden_dist = models.FloatField(default=4023)
    v1_load_rate = models.FloatField(default=35000)
    v1_dis_rate = models.FloatField(default=8000)
    v1_load_factor = models.FloatField(default=1.0)
    v1_dis_factor = models.FloatField(default=1.0)
    v1_turntimes = models.FloatField(default=36)
    v1_port_exp = models.FloatField(default=165000)
    v1_various_exp = models.FloatField(default=10000)

    v2_name = models.CharField(max_length=160, default='Santos to Qingdao')
    v2_ballast_dist = models.FloatField(default=8975)
    v2_laden_dist = models.FloatField(default=11443)
    v2_load_rate = models.FloatField(default=8000)
    v2_dis_rate = models.FloatField(default=8000)
    v2_load_factor = models.FloatField(default=1.35)
    v2_dis_factor = models.FloatField(default=1.5)
    v2_turntimes = models.FloatField(default=36)
    v2_port_exp = models.FloatField(default=160000)
    v2_various_exp = models.FloatField(default=10000)

    class Meta:
        verbose_name = 'Vessel Compare Config'

    def __str__(self):
        return 'Vessel Compare Config'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class ComparisonVessel(models.Model):
    """A vessel entry in the vessel comparison tool."""
    name = models.CharField(max_length=120)
    order = models.PositiveIntegerField(default=0)
    is_standard = models.BooleanField(default=False, help_text='BKI reference vessel')
    intake_v1 = models.FloatField(default=79000)
    intake_v2 = models.FloatField(default=69500)
    laden_speed = models.FloatField(default=12.0)
    ballast_speed = models.FloatField(default=12.5)
    laden_cons = models.FloatField(default=22.0)
    ballast_cons = models.FloatField(default=23.0)
    port_cons = models.FloatField(default=4.5)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'created_at']
        verbose_name = 'Comparison Vessel'
        verbose_name_plural = 'Comparison Vessels'

    def __str__(self):
        return self.name
