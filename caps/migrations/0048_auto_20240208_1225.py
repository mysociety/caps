# Generated by Django 3.2.21 on 2024-02-08 12:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('caps', '0047_auto_20231017_1439'),
    ]

    operations = [
        migrations.AlterField(
            model_name='council',
            name='county',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AlterField(
            model_name='council',
            name='end_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='council',
            name='region',
            field=models.CharField(blank=True, choices=[('East Midlands', 'East Midlands'), ('East of England', 'East of England'), ('London', 'London'), ('North East', 'North East'), ('North West', 'North West'), ('Northern Ireland', 'Northern Ireland'), ('Scotland', 'Scotland'), ('South East', 'South East'), ('South West', 'South West'), ('Wales', 'Wales'), ('West Midlands', 'West Midlands'), ('Yorkshire and The Humber', 'Yorkshire and The Humber')], max_length=200, null=True),
        ),
        migrations.AlterField(
            model_name='council',
            name='replaced_by',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AlterField(
            model_name='council',
            name='start_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='council',
            name='twitter_name',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AlterField(
            model_name='council',
            name='twitter_url',
            field=models.URLField(blank=True, null=True),
        ),
    ]