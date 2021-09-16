# -*- coding: future_fstrings -*-
from os.path import join, basename
from datetime import date
import math
import zipfile

from caps.models import Council, PlanDocument

from django.core.management.base import BaseCommand, CommandError
from django.core.files import File

from django.conf import settings

class Command(BaseCommand):
    help = 'creates a zip file of all the current plans'

    def handle(self, *args, **options):
        print("generating zip file of plan pdfs")

        plan_count = 0
        zip_path = join(settings.MEDIA_ROOT, 'data', 'plans', 'plans.zip')
        csv_file = join(settings.MEDIA_ROOT, 'data', settings.PROCESSED_CSV_NAME)
        plans = PlanDocument.objects.all()
        with zipfile.ZipFile(zip_path, 'w') as zip_file:
            zip_file.write(csv_file, arcname=settings.PROCESSED_CSV_NAME)
            for plan in plans:
                plan_count += 1
                zip_file.write(plan.file.path, arcname=basename(plan.file.path))

        print("zip file with %d plans generated" % plan_count)

