# Generated by Django 3.2.20 on 2023-09-14 13:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scoring', '0008_alter_planquestionscore_score'),
    ]

    operations = [
        migrations.AlterField(
            model_name='plansectionscore',
            name='score',
            field=models.SmallIntegerField(default=0),
        ),
    ]
