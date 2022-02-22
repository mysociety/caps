from os.path import join

import pandas as pd

from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = "processing scottish council climate data"

    def handle(self, *args, **options):
        self.process_data()

    def process_data(self):
        data = join(settings.SCOTTISH_DIR, "data_list.csv")
        df = pd.read_csv(data)

        for index, row in df.iterrows():
            self.process_report(row)

    def process_report(self, data):
        report = join(settings.SCOTTISH_DIR, data["file"])

        xls = pd.ExcelFile(report)
        print(report)
        # check for guide in sheet names as needs to be different
        for sheet_name in xls.sheet_names:
            sheet = pd.read_excel(report, sheet_name)

            titles = sheet.iloc[:, 1]
            try:
                if titles.str.contains(
                    r"Name of (?:the organisation|reporting body)"
                ).any():
                    last = ""
                    for item in titles:
                        if last == "Budget":
                            print("budget is {}".format(item))
                        elif (
                            type(last) is str
                            and last.find("full-time equivalent staff") > -1
                        ):
                            print("FTE count is {}".format(item))
                        last = item
                    print()
                    break
            except:
                print("problem parsing {}".format(sheet_name))
