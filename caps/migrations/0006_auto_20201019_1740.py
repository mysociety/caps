# Generated by Django 2.2.8 on 2020-10-19 17:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('caps', '0005_plandocument_url_hash'),
    ]

    operations = [
        migrations.AlterField(
            model_name='plandocument',
            name='document_type',
            field=models.PositiveSmallIntegerField(blank=True, choices=[(1, 'Action plan'), (2, 'Climate strategy'), (3, 'Summary document'), (4, 'Pre-plan'), (5, 'Meeting minutes')], null=True),
        ),
    ]
