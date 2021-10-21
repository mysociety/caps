# -*- coding: future_fstrings -*-
from os.path import join

import requests

import pandas as pd

from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings
from django.db.models import Count

from caps.models import Council, DataType, DataPoint

EMISSIONS_XLS_URL = 'https://assets.publishing.service.gov.uk/government/uploads/system/uploads/attachment_data/file/894787/2005-18-uk-local-regional-co2-emissions.xlsx'

EMISSIONS_XLS_NAME = '2005-18-uk-local-regional-co2-emissions.xlsx'
EMISSIONS_XLS = join(settings.DATA_DIR, EMISSIONS_XLS_NAME)
EMISSIONS_SHEET = 'Subset dataset'

EMISSIONS_DATA_NAME = 'emissions.csv'
EMISSIONS_DATA = join(settings.DATA_DIR, EMISSIONS_DATA_NAME)

def get_data_files():

    data_files = [(EMISSIONS_XLS_URL, EMISSIONS_XLS)]

    for (source, destination) in data_files:
        r = requests.get(source)
        with open(destination, 'wb') as outfile:
            outfile.write(r.content)


def columns_to_names_and_units():
    return {
        'A. Industry and Commercial Electricity': ('Industry and Commercial Electricity', 'kt CO2'),
        'B. Industry and Commercial Gas': ('Industry and Commercial Gas', 'kt CO2'),
        'C. Large Industrial Installations': ('Large Industrial Installations', 'kt CO2'),
        'D. Industrial and Commercial Other Fuels': ('Industrial and Commercial Other Fuels', 'kt CO2'),
        'E. Agriculture': ('Agriculture', 'kt CO2'),
        'Industry and Commercial Total': ('Industry and Commercial Total', 'kt CO2'),
        'F. Domestic Electricity': ('Domestic Electricity', 'kt CO2'),
        'G. Domestic Gas': ('Domestic Gas', 'kt CO2'),
        "H. Domestic 'Other Fuels'": ("Domestic Other Fuels", 'kt CO2'),
        'Domestic Total': ('Domestic Total', 'kt CO2'),
        'I. Road Transport (A roads)': ('Road Transport (A roads)', 'kt CO2'),
        'K. Road Transport (Minor roads)': ('Road Transport (Minor roads)', 'kt CO2'),
        'M. Transport Other': ('Transport Other', 'kt CO2'),
        'Transport Total': ('Transport Total', 'kt CO2'),
        'Grand Total': ('Total Emissions', 'kt CO2'),
        "Population                                              ('000s, mid-year estimate)": ('Population', '000s'),
        "Per Capita Emissions (t)": ("Per Capita Emissions", 't'),
        "Area (km2)": ("Area", 'km2'),
        "Emissions per km2 (kt)": ("Emissions per km2", 'kt'),
    }

def create_data_types():
    emissions_df = pd.read_csv(EMISSIONS_DATA)

    cols_to_names_and_units = columns_to_names_and_units()
    for column in emissions_df.columns[5:]:
        (name, unit) = cols_to_names_and_units[column]
        data_type, created = DataType.objects.get_or_create(
            name = name,
            source_url = EMISSIONS_XLS_URL,
            name_in_source = column,
            unit = unit
        )

def check_completeness():

    authority_types_without_expected_data = ['COMB', 'CTY']
    councils_with_no_data = Council.objects.exclude(authority_type__in=authority_types_without_expected_data).annotate(num_datapoints=Count('datapoint')).filter(num_datapoints__lt=1)
    for council in councils_with_no_data:
        print(f"No data for {council.name} {council.gss_code}")

def import_emissions_data():
    emissions_df = pd.read_csv(EMISSIONS_DATA)
    error_list = []
    for index, row in emissions_df.iterrows():
        name = row['Name']
        gss_code = row['Code']
        year = row['Year']
        cols_to_names_and_units = columns_to_names_and_units()

        if not name.endswith('Total') and not pd.isnull(row['Code']) and name not in error_list:
            for column in cols_to_names_and_units:
                (data_type_name, _) = cols_to_names_and_units[column]
                try:
                    data_point, created = DataPoint.objects.get_or_create(
                        year = year,
                        value = row[column],
                        council = Council.objects.get(gss_code=gss_code),
                        data_type = DataType.objects.get(name=data_type_name),
                    )
                except ObjectDoesNotExist as err:
                    print(f'{name} {gss_code} {err}')
                    error_list.append(name)
                    break

def convert_emissions_data():

    emissions_df = pd.read_excel(EMISSIONS_XLS, sheet_name=EMISSIONS_SHEET)
    emissions_df.to_csv(EMISSIONS_DATA, index = False, header=False)

class Command(BaseCommand):
    help = 'Imports emissions data by council'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Update all data (slower but more thorough)',
        )
        # useful for when new data comes out and we want to replace it all
        parser.add_argument(
            '--replace',
            action='store_true',
            help='Remove and replace all data (e.g post new source)',
        )

    def handle(self, *args, **options):
        get_all = options['all']
        replace = options['replace']
        if replace:
            print("removing and replacing all data")
            DataPoint.objects.all().delete()
            DataType.objects.all().delete()
        if not get_all and DataPoint.objects.count() > 0:
            print("emissions data exists, skipping")
        else:
            print('getting data files')
            get_data_files()
            print('converting emissions data')
            convert_emissions_data()
            print('creating data types')
            create_data_types()
            print('importing emissions data')
            import_emissions_data()
            print('checking completeness')
            check_completeness()
