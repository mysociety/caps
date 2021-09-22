# -*- coding: future_fstrings -*-
import requests
import urllib3

from time import sleep

import pandas as pd

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import transaction

from caps.models import Council, PlanDocument, EmergencyDeclaration
from caps.import_utils import add_authority_codes, add_gss_codes

import ssl

ssl._create_default_https_context = ssl._create_unverified_context
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

good_data = False

def get_promises():
    # Get the google doc as a CSV file
    sheet_url = f"https://docs.google.com/spreadsheets/d/{settings.DECLARATIONS_CSV_KEY}/gviz/tq?tq=options%20no_format&tqx=out:csv&sheet={settings.DECLARATIONS_CSV_SHEET_NAME}"
    r = requests.get(sheet_url)
    with open(settings.DECLARATIONS_CSV, 'wb') as outfile:
        outfile.write(r.content)

def check_sheet_ok(header):
    global good_data
    df = pd.read_csv(settings.DECLARATIONS_CSV)
    urls = df[header]
    # fail if we have anything that looks like bad data
    if urls.str.contains('#NAME|Loading', regex=True).any():
        print('contains bad data, sleeping for 10 seconds and trying again')
        return False
    # also fail if we have no good data in case there is some other fail condition
    # not covered above
    if not urls.str.contains('^http', regex=True).any():
        print('does not contain good data, sleeping for 10 seconds and trying again')
        return False

    good_data = True
    return True

"""
we are relying on a formula to update the contents of the column which sometimes suffers delays in calculation on
the first attempt so we have to check if the data is there are retry if not. Trial and error suggests that two
retries is enouogh time for google to get the calculations in place
"""
def fetch_promises():
    get_promises()
    count = 1
    while not check_sheet_ok('reference url') and count < 3:
        sleep(10)
        get_promises()
        count = count + 1

    if not good_data:
        print("Failed to get good declarations data, not importing")

# Replace the column header lines
def replace_headers():
    df = pd.read_csv(settings.DECLARATIONS_CSV)
    df = df.dropna(axis='columns', how='all')

    df.columns = ['council',
                  'council_type',
                  'council_region',
                  'control_at_declaration',
                  'control_now',
                  'leader',
                  'proposer',
                  'made_declaration',
                  'date_made',
                  'motion_link',
                  'ref_to_adaptation',
                  'ecological_emergency',
                  'ref_to_nature',
                  'call_to_gov',
                  'carbon_neutral_date',
                  'carbon_neutral_whole_date',
                  'notes',
                  'motion_url']
    df.to_csv(open(settings.DECLARATIONS_CSV, "w"), index=False, header=True)

"""
Wrap this in a transaction and delete all the things as it makes more sense
to just remove and replace everything rather than try and work out what's
changed as we only care about the now.
"""
@transaction.atomic
def import_declarations():
    # if we have any bad data then do not update
    if not check_sheet_ok('motion_url'):
        print("failed to get good data, not updating")
        return

    # just refresh everything
    EmergencyDeclaration.objects.all().delete()

    df = pd.read_csv(settings.DECLARATIONS_CSV)
    for index, row in df.iterrows():
        made_declaration = PlanDocument.char_from_text(row['made_declaration'])
        # skip unless starts with Y
        if not made_declaration.startswith('Y'):
            continue

        gss_code = row['gss_code']
        if pd.isnull(row['gss_code']) or gss_code == 'nan':
            continue

        try:
            council = Council.objects.get(gss_code=gss_code)
        except Council.DoesNotExist:
            print("Could not find council to import declaration: %s" % row['council'], file=sys.stderr)
            continue

        if not pd.isnull(row['motion_url']):

            declaration = EmergencyDeclaration.objects.create(
                council=council,
                date_declared=PlanDocument.date_from_text(row['date_made']),
                source_url=PlanDocument.char_from_text(row['motion_url']),
            )


class Command(BaseCommand):
    help = 'fetch declarations data'

    def handle(self, *args, **options):
        print("getting the declarations csv")
        fetch_promises()
        print("replacing declarations headers")
        replace_headers()
        print("adding council codes to decarations")
        add_authority_codes(settings.DECLARATIONS_CSV)
        add_gss_codes(settings.DECLARATIONS_CSV)
        print("importing the declarations")
        import_declarations()

