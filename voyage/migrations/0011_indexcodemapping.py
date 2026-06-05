from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('voyage', '0010_dynamic_voyages'),
    ]

    operations = [
        migrations.CreateModel(
            name='IndexCodeMapping',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rate_code', models.CharField(max_length=120, unique=True, help_text='RateCode from Baltic Exchange Excel')),
                ('target_index', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='code_mappings',
                    to='voyage.availableindex',
                    help_text='Leave blank to auto-create a new index using the rate code as name',
                )),
                ('skip', models.BooleanField(default=False, help_text='Do not import this rate code')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Index Code Mapping',
                'verbose_name_plural': 'Index Code Mappings',
                'ordering': ['rate_code'],
            },
        ),
    ]
