from django.db import models


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
