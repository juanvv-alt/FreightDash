from django import forms
from .models import RouteParameters


class RouteParametersForm(forms.ModelForm):
    """Form for editing route parameters"""
    
    class Meta:
        model = RouteParameters
        fields = [
            'ballast_distance', 'laden_distance', 'intake', 'load_rate',
            'discharge_rate', 'turntime_hours', 'port_exp_load_port',
            'port_exp_discharge_port', 'freight_commission_pct', 'sea_margin_pct',
            'ballast_speed', 'laden_speed', 'ballast_consumption',
            'laden_consumption', 'port_consumption'
        ]
        widgets = {
            field: forms.NumberInput(attrs={'step': 'any', 'class': 'form-control'})
            for field in fields
        }


class TCECalculatorForm(forms.Form):
    """Form for TCE calculator inputs"""
    route = forms.ChoiceField(
        choices=[],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, route_choices=None, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [('', '-- Choose a route --')]
        if route_choices:
            choices.extend(route_choices)
        self.fields['route'].choices = choices
    
    # Distance and cargo parameters
    ballast_distance = forms.FloatField(
        widget=forms.NumberInput(attrs={'step': 'any', 'class': 'form-control'})
    )
    laden_distance = forms.FloatField(
        widget=forms.NumberInput(attrs={'step': 'any', 'class': 'form-control'})
    )
    intake = forms.FloatField(
        widget=forms.NumberInput(attrs={'step': 'any', 'class': 'form-control'})
    )
    load_rate = forms.FloatField(
        widget=forms.NumberInput(attrs={'step': 'any', 'class': 'form-control'})
    )
    discharge_rate = forms.FloatField(
        widget=forms.NumberInput(attrs={'step': 'any', 'class': 'form-control'})
    )
    turntime_hours = forms.FloatField(
        widget=forms.NumberInput(attrs={'step': 'any', 'class': 'form-control'})
    )
    
    # Port expenses
    port_exp_load_port = forms.FloatField(
        widget=forms.NumberInput(attrs={'step': 'any', 'class': 'form-control'})
    )
    port_exp_discharge_port = forms.FloatField(
        widget=forms.NumberInput(attrs={'step': 'any', 'class': 'form-control'})
    )
    
    # Commission and margins
    freight_commission_pct = forms.FloatField(
        widget=forms.NumberInput(attrs={'step': 'any', 'class': 'form-control'})
    )
    sea_margin_pct = forms.FloatField(
        widget=forms.NumberInput(attrs={'step': 'any', 'class': 'form-control'})
    )
    
    # Speed parameters
    ballast_speed = forms.FloatField(
        widget=forms.NumberInput(attrs={'step': 'any', 'class': 'form-control'})
    )
    laden_speed = forms.FloatField(
        widget=forms.NumberInput(attrs={'step': 'any', 'class': 'form-control'})
    )
    
    # Consumption parameters
    ballast_consumption = forms.FloatField(
        widget=forms.NumberInput(attrs={'step': 'any', 'class': 'form-control'})
    )
    laden_consumption = forms.FloatField(
        widget=forms.NumberInput(attrs={'step': 'any', 'class': 'form-control'})
    )
    port_consumption = forms.FloatField(
        widget=forms.NumberInput(attrs={'step': 'any', 'class': 'form-control'})
    )
    
    # Pricing inputs
    freight_rate = forms.FloatField(
        initial=10.0,
        widget=forms.NumberInput(attrs={'step': 'any', 'class': 'form-control'})
    )
    fuel_price = forms.FloatField(
        initial=495.0,
        widget=forms.NumberInput(attrs={'step': 'any', 'class': 'form-control'})
    )
    tce_field = forms.FloatField(
        initial=0.0,
        widget=forms.NumberInput(attrs={'step': 'any', 'class': 'form-control'})
    )
