"""
Replace hardcoded v1/v2 voyage fields with a proper ComparisonVoyage table
and a VesselVoyageIntake junction. Data is migrated from the old columns.
"""
from django.db import migrations, models
import django.db.models.deletion


SEED_VOYAGES = [
    {
        'name': 'Abbot Point to VN', 'order': 0,
        'ballast_dist': 3734, 'laden_dist': 4023,
        'load_rate': 35000, 'dis_rate': 8000,
        'load_factor': 1.0, 'dis_factor': 1.0,
        'turntimes_hours': 36, 'port_exp': 165000, 'various_exp': 10000,
    },
    {
        'name': 'Santos to Qingdao', 'order': 1,
        'ballast_dist': 8975, 'laden_dist': 11443,
        'load_rate': 8000, 'dis_rate': 8000,
        'load_factor': 1.35, 'dis_factor': 1.5,
        'turntimes_hours': 36, 'port_exp': 160000, 'various_exp': 10000,
    },
]


def migrate_data(apps, schema_editor):
    ComparisonVoyage = apps.get_model('voyage', 'ComparisonVoyage')
    ComparisonVessel = apps.get_model('voyage', 'ComparisonVessel')
    VesselVoyageIntake = apps.get_model('voyage', 'VesselVoyageIntake')

    # Create the two default voyages
    voyages = []
    for vd in SEED_VOYAGES:
        v, _ = ComparisonVoyage.objects.get_or_create(
            name=vd['name'],
            defaults={k: val for k, val in vd.items() if k != 'name'},
        )
        voyages.append(v)

    # Migrate existing per-vessel intakes from old intake_v1/intake_v2 columns
    for vessel in ComparisonVessel.objects.all():
        old_v1 = getattr(vessel, 'intake_v1', vessel.default_intake)
        old_v2 = getattr(vessel, 'intake_v2', vessel.default_intake)
        old_intakes = [old_v1, old_v2]
        for i, voyage in enumerate(voyages):
            intake_val = old_intakes[i] if i < len(old_intakes) else vessel.default_intake
            VesselVoyageIntake.objects.get_or_create(
                vessel=vessel, voyage=voyage,
                defaults={'intake': intake_val},
            )


def reverse_migrate(apps, schema_editor):
    apps.get_model('voyage', 'ComparisonVoyage').objects.all().delete()
    apps.get_model('voyage', 'VesselVoyageIntake').objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('voyage', '0009_comparisonvessel_vesselcompareconfig'),
    ]

    operations = [
        # 1. Create ComparisonVoyage table
        migrations.CreateModel(
            name='ComparisonVoyage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=160)),
                ('order', models.PositiveIntegerField(default=0)),
                ('ballast_dist', models.FloatField(default=5000)),
                ('laden_dist', models.FloatField(default=5000)),
                ('load_rate', models.FloatField(default=10000)),
                ('dis_rate', models.FloatField(default=10000)),
                ('load_factor', models.FloatField(default=1.0)),
                ('dis_factor', models.FloatField(default=1.0)),
                ('turntimes_hours', models.FloatField(default=36)),
                ('port_exp', models.FloatField(default=100000)),
                ('various_exp', models.FloatField(default=10000)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'ordering': ['order', 'created_at'], 'verbose_name': 'Comparison Voyage', 'verbose_name_plural': 'Comparison Voyages'},
        ),

        # 2. Add default_intake to ComparisonVessel
        migrations.AddField(
            model_name='comparisonvessel',
            name='default_intake',
            field=models.FloatField(default=79000, help_text='Used when no voyage-specific intake is set'),
        ),

        # 3. Create VesselVoyageIntake junction table
        migrations.CreateModel(
            name='VesselVoyageIntake',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('intake', models.FloatField(default=79000)),
                ('vessel', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='voyage_intakes', to='voyage.comparisonvessel')),
                ('voyage', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='vessel_intakes', to='voyage.comparisonvoyage')),
            ],
            options={'verbose_name': 'Vessel Voyage Intake', 'unique_together': {('vessel', 'voyage')}},
        ),

        # 4. Migrate data: seed voyages + create intake records from old v1/v2 columns
        migrations.RunPython(migrate_data, reverse_migrate),

        # 5. Remove old voyage columns from VesselCompareConfig
        migrations.RemoveField(model_name='vesselcompareconfig', name='v1_name'),
        migrations.RemoveField(model_name='vesselcompareconfig', name='v1_ballast_dist'),
        migrations.RemoveField(model_name='vesselcompareconfig', name='v1_laden_dist'),
        migrations.RemoveField(model_name='vesselcompareconfig', name='v1_load_rate'),
        migrations.RemoveField(model_name='vesselcompareconfig', name='v1_dis_rate'),
        migrations.RemoveField(model_name='vesselcompareconfig', name='v1_load_factor'),
        migrations.RemoveField(model_name='vesselcompareconfig', name='v1_dis_factor'),
        migrations.RemoveField(model_name='vesselcompareconfig', name='v1_turntimes'),
        migrations.RemoveField(model_name='vesselcompareconfig', name='v1_port_exp'),
        migrations.RemoveField(model_name='vesselcompareconfig', name='v1_various_exp'),
        migrations.RemoveField(model_name='vesselcompareconfig', name='v2_name'),
        migrations.RemoveField(model_name='vesselcompareconfig', name='v2_ballast_dist'),
        migrations.RemoveField(model_name='vesselcompareconfig', name='v2_laden_dist'),
        migrations.RemoveField(model_name='vesselcompareconfig', name='v2_load_rate'),
        migrations.RemoveField(model_name='vesselcompareconfig', name='v2_dis_rate'),
        migrations.RemoveField(model_name='vesselcompareconfig', name='v2_load_factor'),
        migrations.RemoveField(model_name='vesselcompareconfig', name='v2_dis_factor'),
        migrations.RemoveField(model_name='vesselcompareconfig', name='v2_turntimes'),
        migrations.RemoveField(model_name='vesselcompareconfig', name='v2_port_exp'),
        migrations.RemoveField(model_name='vesselcompareconfig', name='v2_various_exp'),

        # 6. Remove old intake_v1/intake_v2 from ComparisonVessel
        migrations.RemoveField(model_name='comparisonvessel', name='intake_v1'),
        migrations.RemoveField(model_name='comparisonvessel', name='intake_v2'),
    ]
