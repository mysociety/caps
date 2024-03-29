# Generated by Django 3.2.21 on 2023-10-17 14:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('caps', '0046_cachedsearch_keyphrase_keyphrasepairwise'),
    ]

    operations = [
        migrations.AlterField(
            model_name='historicalplandocument',
            name='document_type',
            field=models.PositiveSmallIntegerField(blank=True, choices=[('-1', 'All document types'), (1, 'Action plan'), (2, 'Climate strategy'), (3, 'Summary document'), (4, 'Pre-plan'), (5, 'Meeting minutes'), (6, 'Biodiversity plan'), (7, 'Baseline review'), (8, 'Supporting evidence'), (9, 'Engagement plan'), (10, 'Other plan'), (11, 'Progress report'), (12, "Citizens' assembly")], null=True),
        ),
        migrations.AlterField(
            model_name='plandocument',
            name='document_type',
            field=models.PositiveSmallIntegerField(blank=True, choices=[('-1', 'All document types'), (1, 'Action plan'), (2, 'Climate strategy'), (3, 'Summary document'), (4, 'Pre-plan'), (5, 'Meeting minutes'), (6, 'Biodiversity plan'), (7, 'Baseline review'), (8, 'Supporting evidence'), (9, 'Engagement plan'), (10, 'Other plan'), (11, 'Progress report'), (12, "Citizens' assembly")], null=True),
        ),
    ]
