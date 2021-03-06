# Generated by Django 2.2.8 on 2020-10-16 15:37

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Council',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateField(auto_now_add=True)),
                ('updated_at', models.DateField(auto_now=True)),
                ('name', models.CharField(max_length=100)),
                ('slug', models.SlugField(max_length=100)),
                ('authority_code', models.CharField(max_length=3)),
                ('authority_type', models.CharField(max_length=4)),
                ('whatdotheyknow_id', models.IntegerField()),
                ('mapit_id', models.CharField(max_length=3)),
                ('website_url', models.URLField()),
            ],
        ),
        migrations.CreateModel(
            name='PlanDocument',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateField(auto_now_add=True)),
                ('updated_at', models.DateField(auto_now=True)),
                ('url', models.URLField()),
                ('date_first_found', models.DateField(blank=True, null=True)),
                ('date_last_found', models.DateField(blank=True, null=True)),
                ('start_year', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('end_year', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('document_type', models.PositiveSmallIntegerField(choices=[(1, 'Action plan'), (2, 'Climate strategy'), (3, 'Summary document'), (4, 'Pre plan'), (5, 'Meeting minutes')])),
                ('scope', models.PositiveSmallIntegerField(blank=True, choices=[(1, 'Council only'), (2, 'Whole area')], null=True)),
                ('status', models.PositiveSmallIntegerField(blank=True, choices=[(1, 'Draft'), (2, 'Approved')], null=True)),
                ('well_presented', models.BooleanField(blank=True)),
                ('baseline_analysis', models.BooleanField(blank=True, null=True)),
                ('notes', models.CharField(blank=True, max_length=500)),
                ('file_type', models.CharField(max_length=200)),
                ('charset', models.CharField(blank=True, max_length=50)),
                ('text', models.TextField(blank=True)),
                ('file', models.FileField(upload_to='', verbose_name='plans')),
                ('council', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='caps.Council')),
            ],
        ),
    ]
