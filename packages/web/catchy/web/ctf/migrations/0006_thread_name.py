from django.db import migrations, models

import catchy.web.ctf.models


def backfill_thread_names(apps, schema_editor):
    thread_model = apps.get_model("ctf", "Thread")
    for thread in thread_model.objects.filter(name="").only("pk"):
        thread_model.objects.filter(pk=thread.pk).update(
            name=catchy.web.ctf.models.generate_thread_name()
        )


def clear_thread_names(apps, schema_editor):
    apps.get_model("ctf", "Thread").objects.update(name="")


class Migration(migrations.Migration):
    dependencies = [
        ("ctf", "0005_thread_is_public"),
    ]

    operations = [
        migrations.AddField(
            model_name="thread",
            name="name",
            field=models.SlugField(blank=True, default="", max_length=80),
        ),
        migrations.RunPython(backfill_thread_names, clear_thread_names),
        migrations.AlterField(
            model_name="thread",
            name="name",
            field=models.SlugField(
                blank=True,
                default=catchy.web.ctf.models.generate_thread_name,
                max_length=80,
            ),
        ),
    ]
