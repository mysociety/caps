# -*- coding: future_fstrings -*-
from os.path import join, basename, splitext, isfile

import requests

import pandas as pd

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


from caps.import_utils import get_data_files, add_extra_authority_info, add_authority_codes, add_combined_authority_gss_codes


def add_missing_authorities():
    plans_df = pd.read_csv(settings.PROCESSED_CSV)
    manual_codes = { 'West Yorkshire Combined Authority': ['WYCA', 'COMB', '52339', 'England'],
                     'North East Combined Authority': ['NECA', 'COMB', '52428', 'England'],
                     'Newcastle Upon Tyne, North Tyneside and Northumberland Combined Authority': ['NTCA', 'COMB', '91532', 'England']
                    }

    missing_councils = []
    for index, row in plans_df[plans_df['authority_code'].isnull()].iterrows():
        council = row['council']
        authority_code = row['authority_code']

        if council in manual_codes:
            plans_df.at[index, 'authority_code'] = manual_codes[council][0]
            plans_df.at[index, 'authority_type'] = manual_codes[council][1]
            plans_df.at[index, 'wdtk_id'] = manual_codes[council][2]
            plans_df.at[index, 'country'] = manual_codes[council][3]
        else:
            missing_councils.append(council)

    plans_df.to_csv(open(settings.PROCESSED_CSV, "w"), index=False, header=True)
    print(f"Councils without authority codes {len(missing_councils)}")
    print(missing_councils)

class Command(BaseCommand):
    help = 'Adds authority codes to the csv of plans'

    def handle(self, *args, **options):
        print('getting data files')
        get_data_files()
        print('adding authority codes')
        add_authority_codes(settings.PROCESSED_CSV)
        print('adding authority info')
        add_extra_authority_info(settings.PROCESSED_CSV)
        print('adding missing authorities')
        add_missing_authorities()
        print('adding combined authority codes')
        add_combined_authority_gss_codes(settings.PROCESSED_CSV)
