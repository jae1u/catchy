from django.db import migrations


def rebuild_sqlite_yaml_tables(apps, schema_editor):
    if schema_editor.connection.vendor != "sqlite":
        return

    statements = [
        "PRAGMA foreign_keys=OFF",
        """
        CREATE TABLE "ctf_ctf_new" (
            "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
            "created_at" datetime NOT NULL,
            "updated_at" datetime NOT NULL,
            "title" varchar(200) NOT NULL,
            "slug" varchar(50) NOT NULL UNIQUE,
            "description" text NOT NULL,
            "settings" text NOT NULL,
            "created_by_id" integer NULL
                REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED
        )
        """,
        """
        INSERT INTO "ctf_ctf_new" (
            "id", "created_at", "updated_at", "title", "slug", "description",
            "settings", "created_by_id"
        )
        SELECT
            "id", "created_at", "updated_at", "title", "slug", "description",
            "settings", "created_by_id"
        FROM "ctf_ctf"
        """,
        'DROP TABLE "ctf_ctf"',
        'ALTER TABLE "ctf_ctf_new" RENAME TO "ctf_ctf"',
        """
        CREATE TABLE "ctf_challenge_new" (
            "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
            "created_at" datetime NOT NULL,
            "updated_at" datetime NOT NULL,
            "challenge_id" varchar(50) NOT NULL,
            "description" text NOT NULL,
            "webhook" text NOT NULL,
            "config" text NOT NULL,
            "source_archive" varchar(100) NOT NULL,
            "created_by_id" integer NULL
                REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED,
            "ctf_id" bigint NOT NULL
                REFERENCES "ctf_ctf" ("id") DEFERRABLE INITIALLY DEFERRED
        )
        """,
        """
        INSERT INTO "ctf_challenge_new" (
            "id", "created_at", "updated_at", "challenge_id", "description",
            "webhook", "config", "source_archive", "created_by_id", "ctf_id"
        )
        SELECT
            "id", "created_at", "updated_at", "challenge_id", "description",
            "webhook", "config", "source_archive", "created_by_id", "ctf_id"
        FROM "ctf_challenge"
        """,
        'DROP TABLE "ctf_challenge"',
        'ALTER TABLE "ctf_challenge_new" RENAME TO "ctf_challenge"',
        'CREATE INDEX "ctf_ctf_created_by_id_fbcb1abe" ON "ctf_ctf" ("created_by_id")',
        """
        CREATE UNIQUE INDEX "ctf_challenge_ctf_id_challenge_id_722144e4_uniq"
        ON "ctf_challenge" ("ctf_id", "challenge_id")
        """,
        'CREATE INDEX "ctf_challenge_challenge_id_8c6b7fe7" ON "ctf_challenge" ("challenge_id")',
        'CREATE INDEX "ctf_challenge_created_by_id_1c6378c8" ON "ctf_challenge" ("created_by_id")',
        'CREATE INDEX "ctf_challenge_ctf_id_f67a13f0" ON "ctf_challenge" ("ctf_id")',
        "PRAGMA foreign_keys=ON",
    ]

    with schema_editor.connection.cursor() as cursor:
        for statement in statements:
            cursor.execute(statement)


class Migration(migrations.Migration):
    dependencies = [
        ("ctf", "0002_use_yaml_text_fields"),
    ]

    operations = [
        migrations.RunPython(
            rebuild_sqlite_yaml_tables,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
