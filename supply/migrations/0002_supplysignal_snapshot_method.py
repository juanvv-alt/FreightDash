from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("supply", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="supplysignal",
            name="method",
            field=models.CharField(
                choices=[
                    ("regression", "Regression"),
                    ("zscore", "Z-score heuristic"),
                    ("snapshot", "Snapshot ratio (cold start)"),
                    ("insufficient", "Insufficient data"),
                ],
                max_length=20,
            ),
        ),
    ]
