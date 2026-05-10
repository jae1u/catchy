from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ctf", "0004_steeringmessage"),
    ]

    operations = [
        migrations.AddField(
            model_name="thread",
            name="is_public",
            field=models.BooleanField(default=False),
        ),
    ]
