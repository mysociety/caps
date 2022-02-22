from os.path import join
from time import sleep
import glob

import requests
from urllib.parse import urljoin
import urllib.request
import urllib3

from bs4 import BeautifulSoup

from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils.text import slugify

import ssl


BASE_URL = "https://sustainablescotlandnetwork.org/"

ssl._create_default_https_context = ssl._create_unverified_context
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)




class Command(BaseCommand):
    help = "fetch scottish council climate data"

    def handle(self, *args, **options):
        print("getting scottish council climate data")
        self.fetch_all_reports()

    def get_dom(self, url):
        local_filename, headers = urllib.request.urlretrieve(url)

        with open(local_filename, "r") as reader:
            page = reader.read()

        return BeautifulSoup(page, "html.parser")


    def fetch_all_reports(self):
        index_url = "https://sustainablescotlandnetwork.org/reports?_=1645526681566&filterrific%5Bwith_category_id%5D=6"

        while index_url is not None:
            index_url = self.paginate_list(index_url)


    def paginate_list(self, index_url):
        try:
            dom = self.get_dom(index_url)
        except Exception as e:
            print("problem getting list of councils: {}".format(e))
            return None

        self.process_councils_on_page(dom)
        pagination = dom.find("nav", class_="pagination")
        next_page = pagination.find("span", class_="next")
        if next_page:
            next_link = next_page.find("a")
            return urljoin(BASE_URL, next_link["href"])

        return None


    def process_councils_on_page(self, dom):
        councils = dom.find_all("div", class_="report__index-text")
        for council in councils:
            link = council.find("a")["href"]
            link = urljoin(BASE_URL, link)
            self.get_reports_from_page(link)


    def get_reports_from_page(self, url):
        dom = self.get_dom(url)
        links = dom.find_all("a", class_="spreadsheet__link")
        for link in links:
            url = link["href"]
            text = link.text
            url = urljoin(BASE_URL, url)
            filename = slugify(text)
            local_path = join(settings.SCOTTISH_DIR, filename)
            if glob.glob("{}.*".format(local_path)):
                print("{} already fetched".format(filename))
                continue
            self.get_document(url, filename)
            sleep(1)


    def get_file_type(self, content_type):
        content_type = content_type.lower()
        content_type_info = content_type.split(";", 2)
        content_file_type = content_type_info[0].strip()

        if content_file_type == "application/pdf":
            file_type = "pdf"
        elif content_file_type == "text/html":
            file_type = "html"
        elif (
            content_type
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ):
            file_type = "xlsx"
        elif content_type == "application/vnd.ms-excel.sheet.macroenabled.12":
            file_type = "xlsm"
        else:
            file_type = None
            print("Unknown content type: " + content_type)

        return file_type


    def get_document(self, url, filename):
        headers = {
            "User-Agent": "mySociety Council climate action plans search",
        }
        try:
            r = requests.get(url, headers=headers, verify=False)
            r.raise_for_status()
            file_type = self.get_file_type(r.headers.get("content-type"))
            filename = "{}.{}".format(filename, file_type)
            local_path = join(settings.SCOTTISH_DIR, filename)
            with open(local_path, "wb") as outfile:
                outfile.write(r.content)
        except requests.exceptions.RequestException as err:
            print(f"Error {filename} {url}: {err}")

        return filename
