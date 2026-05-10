from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ctf", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="ctf",
            name="settings",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AlterField(
            model_name="challenge",
            name="webhook",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AlterField(
            model_name="challenge",
            name="config",
            field=models.TextField(blank=True, default=""),
        ),
    ]
