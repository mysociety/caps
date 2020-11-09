# -*- coding: future_fstrings -*-
from django.core.management.base import BaseCommand, CommandError

from caps.mapit import MapIt, NotFoundException, BadRequestException, InternalServerErrorException, ForbiddenException
from caps.models import Council

from django.db.models import Count

import time

def add_related_councils():
    mapit = MapIt()
    # MapIt doesn't currently have information on Combined Authorities
    councils = Council.objects.exclude(authority_type='COMB')
    for council in councils:
        try:
            mapit_id = mapit.gss_code_to_mapit_id(council.gss_code)
            time.sleep(2)
            touching_gss_codes = mapit.mapit_id_to_touches(mapit_id)
            time.sleep(2)
            for touching_council in Council.objects.filter(gss_code__in=touching_gss_codes):
                council.related_councils.add(touching_council)
            if council.combined_authority:
                council.related_councils.add(council.combined_authority)
            council.save()
        except (NotFoundException, BadRequestException, InternalServerErrorException, ForbiddenException) as error:
            print(f"Error: {council.name} - '{error}'")

class Command(BaseCommand):
    help = 'Adds geographically related authorities for each council using MapIt'

    def handle(self, *args, **options):
        print('adding related authorities')
        add_related_councils()
