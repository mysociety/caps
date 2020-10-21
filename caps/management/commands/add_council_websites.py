# -*- coding: future_fstrings -*-
import urllib.request
import csv
from os.path import join

import pandas as pd

from bs4 import BeautifulSoup

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

WEBSITES_CSV_NAME = 'council_websites.csv'
WEBSITE_CSV = join(settings.DATA_DIR, WEBSITES_CSV_NAME)


def get_dom(url):
    local_filename, headers = urllib.request.urlretrieve(url)

    with open(local_filename, 'r') as reader:
        page = reader.read()

    return BeautifulSoup(page, 'html.parser')

def get_england_and_wales():

    councils = []
    index_url = 'https://www.local.gov.uk/our-support/guidance-and-resources/communications-support/digital-councils/social-media/go-further/a-z-councils-online'

    dom = get_dom(index_url)
    table = dom.find('div', class_='table-responsive')
    body = table.find('tbody')
    rows = body.find_all('tr')
    for row in rows:
        link = row.find('td').find('a')
        council = link.text
        website_url = link['href']
        councils.append({'council': council, 'url': website_url})
    return councils

def get_scotland():

    councils = []
    index_url = 'https://www.cosla.gov.uk/councils'
    dom = get_dom(index_url)
    items = dom.find_all('a', class_='councils__list__item')
    for item in items:
        council = item.find('h4').text
        website_url = item['href']
        councils.append({'council': council, 'url': website_url})
    return councils

def get_combined_authorities():

    councils = []
    index_url = 'https://www.local.gov.uk/topics/devolution/devolution-online-hub/devolution-explained/combined-authorities'
    dom = get_dom(index_url)
    wrapper = dom.find('div', class_='col-md-8')
    list_elements = wrapper.find_all('li')
    for list_element in list_elements:
        link = list_element.find('a')
        council = link.text.strip()
        website_url = link['href']
        if not 'Combined Authority' in council:
            council = council + ' Combined Authority'
        councils.append({'council': council, 'url': website_url})
    return councils

def get_unindexed():
    return [
            {'council': 'Bournemouth, Christchurch and Poole Borough Council',
             'url': 'https://www.bcpcouncil.gov.uk/'},
            {'council': 'Oadby and Wigston Borough Council',
             'url': 'https://www.oadby-wigston.gov.uk/'},
            {'council': 'Folkestone and Hythe District Council',
             'url': 'https://www.folkestone-hythe.gov.uk/'},
            {'council': 'Somerset West and Taunton Council',
             'url': 'https://www.somersetwestandtaunton.gov.uk/'},
            {'council': 'West Suffolk Council',
             'url': 'https://www.westsuffolk.gov.uk/'},
            {'council': 'Newcastle Upon Tyne, North Tyneside and Northumberland Combined Authority',
             'url': 'https://www.northoftyne-ca.gov.uk/'}
           ]

def alternative_names(council_name):
    alternative_mappings = {'Swansea City Council': 'Swansea City and Borough Council'}
    alternative_names = [council_name, council_name.replace('The ', '')]
    if alternative_mappings.get(council_name):
        alternative_names.append(alternative_mappings.get(council_name))
    return alternative_names

def create_council_website_csv():

    all_authorities = []
    all_authorities.append(get_england_and_wales())
    all_authorities.append(get_scotland())
    all_authorities.append(get_combined_authorities())
    all_authorities.append(get_unindexed())

    all_authorities = [item for sublist in all_authorities for item in sublist]

    with open(WEBSITE_CSV, 'w') as csvfile:

        fieldnames = ['council', 'url']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for council_info in all_authorities:
            writer.writerow({'council': council_info['council'], 'url': council_info['url']})

def add_website_urls_to_councils():

    reader = csv.reader(open(WEBSITE_CSV))

    websites = {}
    for row in reader:
        websites[row[0]] = row[1]

    df = pd.read_csv(settings.PROCESSED_CSV)
    rows = len(df['council'])
    df['website_url'] = pd.Series([None] * rows, index=df.index)

    unmatched = []
    for index, row in df.iterrows():
        council_name = row['council']
        alternative_names_set = set(alternative_names(council_name))
        website_set = set(websites)
        matches = list(alternative_names_set.intersection(website_set))
        if matches:
            website_url = websites.get(matches[0])
            df.at[index, 'website_url'] = website_url
        else:
            unmatched.append([council_name, row['authority_type']])
    df.to_csv(open(settings.PROCESSED_CSV, "w"), index=False, header=True)

    if len(unmatched) > 0:
        print(f"{len(unmatched)} councils with no website")
        print(unmatched)

class Command(BaseCommand):
    help = 'Adds website urls to the csv of plans'

    def handle(self, *args, **options):

        print("adding website urls to councils")
        create_council_website_csv()
        add_website_urls_to_councils()
