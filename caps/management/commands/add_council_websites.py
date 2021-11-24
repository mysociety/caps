# -*- coding: future_fstrings -*-
import re
import requests
import urllib.request
import csv
from os.path import join

import pandas as pd

from bs4 import BeautifulSoup

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

WEBSITES_CSV_NAME = 'council_websites.csv'
WEBSITE_CSV = join(settings.DATA_DIR, WEBSITES_CSV_NAME)
SCOTTISH_TWITTER_CSV = join(settings.DATA_DIR, 'scottish_twitter.csv')


def get_dom(url):
    local_filename, headers = urllib.request.urlretrieve(url)

    with open(local_filename, 'r') as reader:
        page = reader.read()

    return BeautifulSoup(page, 'html.parser')

def parse_twitter_name(name):
    name = re.sub(r'^@', '', name)
    return name

def get_england_and_wales():

    councils = []
    index_url = 'https://www.local.gov.uk/our-support/guidance-and-resources/communications-support/digital-councils/social-media/go-further/a-z-councils-online'

    try:
        dom = get_dom(index_url)
    except Exception as e:
        print("problem getting England and Wales URL data: {}".format(e))
        return []

    table = dom.find('div', class_='table-responsive')
    body = table.find('tbody')
    rows = body.find_all('tr')
    for row in rows:
        link = row.find('th').find('a')
        council = link.text
        website_url = link['href']
        twitter_link = row.find('td').find(href=re.compile(r'twitter.com'))
        twitter_url = twitter_link['href']
        twitter_name = parse_twitter_name(twitter_link.text)
        councils.append({'council': council, 'url': website_url, 'twitter_url': twitter_url, 'twitter_name': twitter_name})
    return councils

def get_scotland():

    council_twitter = get_scotland_twitter()
    councils = []
    index_url = 'https://www.cosla.gov.uk/councils'
    try:
        dom = get_dom(index_url)
    except Exception as e:
        print("problem getting Scotland URL data: {}".format(e))
        return []

    items = dom.find_all('a', class_='councils__list__item')
    for item in items:
        council = item.find('h4').text
        website_url = item['href']
        twitter = council_twitter.get(council, {})
        councils.append({
            'council': council,
            'url': website_url,
            'twitter_url': twitter.get('twitter_url', ''),
            'twitter_name': twitter.get('twitter_name', ''),
        })
    return councils

def get_scotland_twitter():
    headers = { 'Accept': 'text/csv' }
    url = 'https://query.wikidata.org/sparql?query=SELECT%20%3Fitem%20%3FitemLabel%20%3Ftwitter%20%20WHERE%20%7B%0A%20%20%3Fitem%20wdt%3AP31%20wd%3AQ21451686%20.%0A%20%20%3Fitem%20wdt%3AP2002%20%3Ftwitter%20.%0A%20%20%20%20SERVICE%20wikibase%3Alabel%20%7B%20bd%3AserviceParam%20wikibase%3Alanguage%20%22%5BAUTO_LANGUAGE%5D%2Cen%22.%20%7D%0A%7D'
    r = requests.get(url, headers=headers)
    with open(SCOTTISH_TWITTER_CSV, 'wb') as outfile:
        outfile.write(r.content)

    councils = {}
    df = pd.read_csv(SCOTTISH_TWITTER_CSV)
    for index, row in df.iterrows():
        councils[row['itemLabel']] = {
            'twitter_name': parse_twitter_name(row['twitter']),
            'twitter_url': 'https://twitter.com/{}'.format(row['twitter']),
        }

    return councils


def get_ni():
    councils = []
    base_url = 'https://www.nidirect.gov.uk'
    index_url = base_url + '/contacts/local-councils-in-northern-ireland'
    try:
        dom = get_dom(index_url)
    except Exception as e:
        print("problem getting Northern Ireland URL data: {}".format(e))
        return []

    table = dom.find('div', class_='item-list')
    rows = table.find_all('span', class_='field-content')
    for row in rows:
        link = row.find('a')
        council = link.text
        contact_url = base_url + link['href']
        contact_page_dom = get_dom(contact_url)
        item = contact_page_dom.find('span', class_='url')
        council_link = item.find('a')['href']
        councils.append({'council': council, 'url': council_link})
    return councils


def get_combined_authorities():

    councils = []
    index_url = 'https://www.local.gov.uk/topics/devolution/devolution-online-hub/devolution-explained/combined-authorities'
    try:
        dom = get_dom(index_url)
    except Exception as e:
        print("problem getting combined authorities URL data: {}".format(e))
        return []

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
             'url': 'https://www.northoftyne-ca.gov.uk/'},
            {'council': 'North Northamptonshire Council',
             'url': 'https://www.northnorthants.gov.uk/'},
            {'council': 'West Northamptonshire Council',
             'url': 'https://www.westnorthants.gov.uk/'},
            {'council': 'Cambridgeshire and Peterborough Combined Authority',
             'url': 'http://www.cambspboroca.org/'},
            {'council': 'Greater Manchester Combined Authority',
             'url': 'https://www.greatermanchester-ca.gov.uk/'},
            {'council': 'Liverpool City Region Combined Authority',
             'url': 'http://www.liverpoolcityregion-ca.gov.uk/'},
            {'council': 'North East Combined Authority',
             'url': 'http://www.northeastca.gov.uk/'},
            {'council': 'Sheffield City Region Combined Authority',
             'url': 'https://sheffieldcityregion.org.uk/'},
            {'council': 'Tees Valley Combined Authority',
             'url': 'https://teesvalley-ca.gov.uk/'},
            {'council': 'West of England Combined Authority',
             'url': 'https://www.westofengland-ca.org.uk/'},
            {'council': 'West Midlands Combined Authority',
             'url': 'https://westmidlandscombinedauthority.org.uk/'},
            {'council': 'West Yorkshire Combined Authority',
             'url': 'https://www.westyorks-ca.gov.uk/'},
           ]

def alternative_names(council_name):
    alternative_mappings = {
        'Swansea City Council': 'Swansea City and Borough Council',
        'Buckinghamshire Council': 'Buckinghamshire County Council',
        'Dorset Council': 'Dorset County Council',
        'West Yorkshire Combined Authority': 'West Yorkshire (@WestYorkshireCA) Combined Authority',
        'Sheffield City Region Combined Authority': 'South Yorkshire (@SheffCityRegion) Combined Authority',
        'Mid Ulster District Council': 'Mid Ulster District Council - Dungannon',
        'Fermanagh and Omagh District Council': 'Fermanagh and Omagh District Council - Enniskillen Office'
    }
    alternative_names = [council_name, council_name.replace('The ', '')]
    if alternative_mappings.get(council_name):
        alternative_names.append(alternative_mappings.get(council_name))
    return alternative_names

def create_council_website_csv():

    all_authorities = []
    all_authorities.append(get_england_and_wales())
    all_authorities.append(get_scotland())
    all_authorities.append(get_combined_authorities())
    all_authorities.append(get_ni())
    all_authorities.append(get_unindexed())

    all_authorities = [item for sublist in all_authorities for item in sublist]

    with open(WEBSITE_CSV, 'w') as csvfile:

        fieldnames = ['council', 'url', 'twitter_url', 'twitter_name']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for council_info in all_authorities:
            writer.writerow({
                'council': council_info['council'],
                'url': council_info['url'],
                'twitter_url': council_info.get('twitter_url', ''),
                'twitter_name': council_info.get('twitter_name', ''),
            })

def add_website_urls_to_councils():

    reader = csv.reader(open(WEBSITE_CSV))

    websites = {}
    for row in reader:
        websites[row[0]] = {
            'url': row[1],
            'twitter_url': row[2],
            'twitter_name': row[3],
        }

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
            details = websites.get(matches[0])
            df.at[index, 'website_url'] = details.get('url', '')
            df.at[index, 'twitter_url'] = details.get('twitter_url', '')
            df.at[index, 'twitter_name'] = details.get('twitter_name', '')
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
