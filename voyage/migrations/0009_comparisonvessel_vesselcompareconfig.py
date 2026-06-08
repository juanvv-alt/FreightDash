from django.db import migrations, models


SEED_VESSELS = [
    {'name': 'BKI',             'order': 0,  'is_standard': True,  'intake_v1': 79000, 'intake_v2': 69500, 'laden_speed': 11.5, 'ballast_speed': 12.5,  'laden_cons': 22.0, 'ballast_cons': 23.0,  'port_cons': 4.5},
    {'name': 'Yangze 22',       'order': 1,  'is_standard': False, 'intake_v1': 79000, 'intake_v2': 69500, 'laden_speed': 12.0, 'ballast_speed': 12.0,  'laden_cons': 22.0, 'ballast_cons': 18.5,  'port_cons': 5.0},
    {'name': 'AQUASALWADOR',    'order': 2,  'is_standard': False, 'intake_v1': 79000, 'intake_v2': 69500, 'laden_speed': 12.25,'ballast_speed': 13.25, 'laden_cons': 22.8, 'ballast_cons': 22.8,  'port_cons': 5.6},
    {'name': 'ZAKYNTHOS',       'order': 3,  'is_standard': False, 'intake_v1': 79000, 'intake_v2': 69500, 'laden_speed': 11.0, 'ballast_speed': 12.0,  'laden_cons': 18.0, 'ballast_cons': 16.5,  'port_cons': 4.0},
    {'name': 'SEACON HAMBURG',  'order': 4,  'is_standard': False, 'intake_v1': 81000, 'intake_v2': 69500, 'laden_speed': 12.0, 'ballast_speed': 12.5,  'laden_cons': 21.5, 'ballast_cons': 20.0,  'port_cons': 5.5},
    {'name': 'Xing Huan Hai',   'order': 5,  'is_standard': False, 'intake_v1': 81000, 'intake_v2': 69500, 'laden_speed': 12.0, 'ballast_speed': 13.0,  'laden_cons': 22.5, 'ballast_cons': 20.5,  'port_cons': 4.5},
    {'name': 'Lestari Tbn',     'order': 6,  'is_standard': False, 'intake_v1': 79000, 'intake_v2': 69500, 'laden_speed': 12.0, 'ballast_speed': 12.0,  'laden_cons': 22.0, 'ballast_cons': 16.5,  'port_cons': 4.2},
    {'name': 'XING HUAN HAI',   'order': 7,  'is_standard': False, 'intake_v1': 82500, 'intake_v2': 72000, 'laden_speed': 12.0, 'ballast_speed': 13.0,  'laden_cons': 22.5, 'ballast_cons': 20.5,  'port_cons': 5.5},
    {'name': 'Orient Point',    'order': 8,  'is_standard': False, 'intake_v1': 80000, 'intake_v2': 69500, 'laden_speed': 11.0, 'ballast_speed': 12.0,  'laden_cons': 17.2, 'ballast_cons': 15.7,  'port_cons': 4.7},
    {'name': 'RB Jordana',      'order': 9,  'is_standard': False, 'intake_v1': 79000, 'intake_v2': 69500, 'laden_speed': 12.0, 'ballast_speed': 12.0,  'laden_cons': 21.4, 'ballast_cons': 18.2,  'port_cons': 4.0},
    {'name': 'BH ASSEMBLE',     'order': 10, 'is_standard': False, 'intake_v1': 79000, 'intake_v2': 69500, 'laden_speed': 12.0, 'ballast_speed': 12.5,  'laden_cons': 25.5, 'ballast_cons': 23.0,  'port_cons': 5.0},
    {'name': 'golden wave',     'order': 11, 'is_standard': False, 'intake_v1': 82500, 'intake_v2': 72000, 'laden_speed': 12.0, 'ballast_speed': 13.0,  'laden_cons': 22.5, 'ballast_cons': 20.5,  'port_cons': 5.0},
    {'name': 'SEACON HAMBURG 2','order': 12, 'is_standard': False, 'intake_v1': 82500, 'intake_v2': 69500, 'laden_speed': 12.0, 'ballast_speed': 12.5,  'laden_cons': 21.5, 'ballast_cons': 20.0,  'port_cons': 5.0},
    {'name': 'light venture',   'order': 13, 'is_standard': False, 'intake_v1': 79000, 'intake_v2': 69500, 'laden_speed': 12.0, 'ballast_speed': 12.5,  'laden_cons': 24.9, 'ballast_cons': 18.9,  'port_cons': 4.0},
    {'name': 'ASL Galaxy',      'order': 14, 'is_standard': False, 'intake_v1': 79000, 'intake_v2': 69500, 'laden_speed': 12.0, 'ballast_speed': 13.0,  'laden_cons': 24.0, 'ballast_cons': 22.0,  'port_cons': 4.3},
    {'name': 'Yangze 18',       'order': 15, 'is_standard': False, 'intake_v1': 79000, 'intake_v2': 69501, 'laden_speed': 12.0, 'ballast_speed': 12.0,  'laden_cons': 24.5, 'ballast_cons': 21.5,  'port_cons': 4.5},
    {'name': 'SHINE PEARL',     'order': 16, 'is_standard': False, 'intake_v1': 80000, 'intake_v2': 69900, 'laden_speed': 12.0, 'ballast_speed': 12.5,  'laden_cons': 20.5, 'ballast_cons': 17.5,  'port_cons': 3.5},
    {'name': 'Amori',           'order': 17, 'is_standard': False, 'intake_v1': 79000, 'intake_v2': 69500, 'laden_speed': 12.0, 'ballast_speed': 12.5,  'laden_cons': 24.0, 'ballast_cons': 23.0,  'port_cons': 4.0},
    {'name': 'Pan Flower',      'order': 18, 'is_standard': False, 'intake_v1': 79000, 'intake_v2': 69500, 'laden_speed': 11.5, 'ballast_speed': 12.75, 'laden_cons': 25.0, 'ballast_cons': 25.0,  'port_cons': 4.0},
    {'name': 'VSC POSEIDON',    'order': 19, 'is_standard': False, 'intake_v1': 73000, 'intake_v2': 65000, 'laden_speed': 12.0, 'ballast_speed': 12.0,  'laden_cons': 23.5, 'ballast_cons': 19.5,  'port_cons': 3.5},
    {'name': 'Bbg Yongjiang',   'order': 20, 'is_standard': False, 'intake_v1': 80000, 'intake_v2': 69500, 'laden_speed': 12.0, 'ballast_speed': 13.0,  'laden_cons': 19.5, 'ballast_cons': 19.5,  'port_cons': 4.0},
    {'name': 'DL Acacia',       'order': 21, 'is_standard': False, 'intake_v1': 79000, 'intake_v2': 69500, 'laden_speed': 11.5, 'ballast_speed': 12.5,  'laden_cons': 26.0, 'ballast_cons': 26.0,  'port_cons': 4.5},
    {'name': 'America',         'order': 22, 'is_standard': False, 'intake_v1': 79000, 'intake_v2': 69500, 'laden_speed': 12.0, 'ballast_speed': 13.0,  'laden_cons': 20.0, 'ballast_cons': 20.0,  'port_cons': 3.0},
]


def seed(apps, schema_editor):
    ComparisonVessel = apps.get_model('voyage', 'ComparisonVessel')
    VesselCompareConfig = apps.get_model('voyage', 'VesselCompareConfig')
    for v in SEED_VESSELS:
        defaults = {k: val for k, val in v.items() if k != 'name'}
        ComparisonVessel.objects.get_or_create(name=v['name'], defaults=defaults)
    VesselCompareConfig.objects.get_or_create(pk=1)


def unseed(apps, schema_editor):
    apps.get_model('voyage', 'ComparisonVessel').objects.all().delete()
    apps.get_model('voyage', 'VesselCompareConfig').objects.filter(pk=1).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('voyage', '0008_align_menu_structure_for_freight_matrix'),
    ]

    operations = [
        migrations.CreateModel(
            name='VesselCompareConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('hire', models.FloatField(default=23000)),
                ('ifo_price', models.FloatField(default=800)),
                ('mgo_price', models.FloatField(default=1300)),
                ('weather_factor', models.FloatField(default=1.07)),
                ('v1_name', models.CharField(default='Abbot Point to VN', max_length=160)),
                ('v1_ballast_dist', models.FloatField(default=3734)),
                ('v1_laden_dist', models.FloatField(default=4023)),
                ('v1_load_rate', models.FloatField(default=35000)),
                ('v1_dis_rate', models.FloatField(default=8000)),
                ('v1_load_factor', models.FloatField(default=1.0)),
                ('v1_dis_factor', models.FloatField(default=1.0)),
                ('v1_turntimes', models.FloatField(default=36)),
                ('v1_port_exp', models.FloatField(default=165000)),
                ('v1_various_exp', models.FloatField(default=10000)),
                ('v2_name', models.CharField(default='Santos to Qingdao', max_length=160)),
                ('v2_ballast_dist', models.FloatField(default=8975)),
                ('v2_laden_dist', models.FloatField(default=11443)),
                ('v2_load_rate', models.FloatField(default=8000)),
                ('v2_dis_rate', models.FloatField(default=8000)),
                ('v2_load_factor', models.FloatField(default=1.35)),
                ('v2_dis_factor', models.FloatField(default=1.5)),
                ('v2_turntimes', models.FloatField(default=36)),
                ('v2_port_exp', models.FloatField(default=160000)),
                ('v2_various_exp', models.FloatField(default=10000)),
            ],
            options={'verbose_name': 'Vessel Compare Config'},
        ),
        migrations.CreateModel(
            name='ComparisonVessel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120)),
                ('order', models.PositiveIntegerField(default=0)),
                ('is_standard', models.BooleanField(default=False)),
                ('intake_v1', models.FloatField(default=79000)),
                ('intake_v2', models.FloatField(default=69500)),
                ('laden_speed', models.FloatField(default=12.0)),
                ('ballast_speed', models.FloatField(default=12.5)),
                ('laden_cons', models.FloatField(default=22.0)),
                ('ballast_cons', models.FloatField(default=23.0)),
                ('port_cons', models.FloatField(default=4.5)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'ordering': ['order', 'created_at'], 'verbose_name': 'Comparison Vessel', 'verbose_name_plural': 'Comparison Vessels'},
        ),
        migrations.RunPython(seed, unseed),
    ]
