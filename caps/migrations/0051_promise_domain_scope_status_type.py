from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("caps", "0050_fix_related_authorities_and_document_type_state"),
    ]

    # scope used PlanDocument.SCOPE_CHOICES (1 = council only, 2 = whole area),
    # and the new domain choices keep those values, so existing rows need no
    # data migration. The new scope field (emissions scopes) is added after
    # the old one has been renamed out of the way.
    operations = [
        migrations.RenameField(
            model_name="promise",
            old_name="scope",
            new_name="domain",
        ),
        migrations.RenameField(
            model_name="historicalpromise",
            old_name="scope",
            new_name="domain",
        ),
        migrations.AlterField(
            model_name="promise",
            name="domain",
            field=models.PositiveSmallIntegerField(
                blank=True,
                choices=[(1, "Council operations"), (2, "Whole area"), (3, "Unclear")],
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="historicalpromise",
            name="domain",
            field=models.PositiveSmallIntegerField(
                blank=True,
                choices=[(1, "Council operations"), (2, "Whole area"), (3, "Unclear")],
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="promise",
            name="type",
            field=models.PositiveSmallIntegerField(
                choices=[(1, "Promise"), (2, "Withdrawal")], default=1
            ),
        ),
        migrations.AddField(
            model_name="historicalpromise",
            name="type",
            field=models.PositiveSmallIntegerField(
                choices=[(1, "Promise"), (2, "Withdrawal")], default=1
            ),
        ),
        migrations.AddField(
            model_name="promise",
            name="status",
            field=models.PositiveSmallIntegerField(
                choices=[(1, "Latest"), (2, "Superseded"), (3, "Withdrawn")],
                default=1,
            ),
        ),
        migrations.AddField(
            model_name="historicalpromise",
            name="status",
            field=models.PositiveSmallIntegerField(
                choices=[(1, "Latest"), (2, "Superseded"), (3, "Withdrawn")],
                default=1,
            ),
        ),
        migrations.AddField(
            model_name="promise",
            name="scope",
            field=models.PositiveSmallIntegerField(
                choices=[(1, "Not specified"), (2, "Scopes 1 & 2"), (3, "Scope 3")],
                default=1,
            ),
        ),
        migrations.AddField(
            model_name="historicalpromise",
            name="scope",
            field=models.PositiveSmallIntegerField(
                choices=[(1, "Not specified"), (2, "Scopes 1 & 2"), (3, "Scope 3")],
                default=1,
            ),
        ),
        migrations.AddField(
            model_name="promise",
            name="target_text",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="historicalpromise",
            name="target_text",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="promise",
            name="source_date",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="historicalpromise",
            name="source_date",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="promise",
            name="last_checked",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="historicalpromise",
            name="last_checked",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AlterField(
            model_name="promise",
            name="notes",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="historicalpromise",
            name="notes",
            field=models.TextField(blank=True, null=True),
        ),
    ]
