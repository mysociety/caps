from os.path import join

import pandas as pd

from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = "processing scottish council climate data"

    data = []

    def handle(self, *args, **options):
        self.process_data()
        self.save_data()

    def process_data(self):
        data = join(settings.SCOTTISH_DIR, "data_list.csv")
        df = pd.read_csv(data)

        for index, row in df.iterrows():
            try:
                self.process_report(row)
                # if index == 20:
                # break
            except Exception as e:
                print(
                    "problem processing report {} for council {}: {}".format(
                        row["file"], row["council"], e
                    )
                )

    def process_report(self):
        if pd.isna(self.report_data["file"]):
            print(
                "bad file for {} {}".format(
                    self.report_data["council"], self.report_data["start_year"]
                )
            )
            return

        report = join(settings.SCOTTISH_DIR, data["file"])

        xls = pd.ExcelFile(report)
        parsed = {}
        for sheet_name in xls.sheet_names:
            # skip this as it's a title page
            if sheet_name == "Guide":
                continue

            try:
                sheet = pd.read_excel(report, sheet_name)
            except Exception as e:
                print(
                    "problem reading sheet {} for council data in {}: {}".format(
                        sheet_name, report, e
                    )
                )
                return

            if parsed.get("council", 0) != 1:
                fetched = self.extract_council_data_from_sheet(
                    sheet, sheet_name, report, data
                )
                parsed["council"] = fetched

            if parsed.get("emissions", 0) != 1:
                fetched = self.extract_emissions_data_from_sheet(
                    sheet, sheet_name, report, data
                )
                parsed["emissions"] = fetched

    def make_data_point(self, data, point_type, point_value):
        data_point = {
            "council": data["council"],
            "authority_code": data["authority_code"],
            "start_year": data["start_year"],
            "end_year": data["end_year"],
            "data_type": point_type,
            "data_value": point_value,
        }

        return data_point

    def extract_council_data_from_sheet(self, sheet, sheet_name, report, data):
        column = 1

        # doesn't hold any useful data and just generated warnings
        if data["start_year"] == 2014 and sheet_name == "Sheet2":
            return 0

        if data["start_year"] >= 2020:
            column = 2

        if len(sheet.columns) <= column:
            return 0

        try:
            titles = sheet.iloc[:, column]
            if titles.str.contains(
                r"Name of (?:the organisation|reporting body)"
            ).any():
                last = ""
                for item in titles:
                    if last == "Budget":
                        data_point = self.make_data_point(data, "Budget", item)
                        self.data.append(data_point)
                    elif (
                        type(last) is str
                        and last.find("full-time equivalent staff") > -1
                    ):
                        data_point = self.make_data_point(data, "FTE", item)
                        self.data.append(data_point)
                    last = item
                return 1
        except Exception as e:
            print(
                "problem parsing sheet {} for council data in {}: {}".format(
                    sheet_name, report, e
                )
            )

        return 0

    def extract_emissions_data_from_sheet(self, sheet, sheet_name, report, data):
        # doesn't hold any useful data and just generated warnings
        if data["start_year"] == 2014 and sheet_name == "Sheet2":
            return 0

        column = 1
        if data["start_year"] >= 2020:
            column = 2

        if len(sheet.columns) <= column:
            return 0

        try:
            titles = sheet.iloc[:, column]
            if titles.str.contains(r"Baseline Year").any():
                start_count = 0
                end_count = 0
                for index, item in titles.items():
                    if item == "Reference year":
                        start_count = index
                    if start_count > 0 and pd.isna(item):
                        end_count = index
                        break

                emissions = sheet.iloc[start_count:end_count, column:]
                emissions = emissions.dropna(axis="columns", how="all")
                emissions_df = emissions.iloc[1:]
                emissions_df.columns = emissions.iloc[0].values

                for index, row in emissions_df.iterrows():
                    for scope in ["Scope 1", "Scope 2", "Scope 3"]:
                        if pd.isna(row[scope]):
                            continue
                        point_type = "{} emissions ({})".format(scope, row["Year"])
                        data_point = self.make_data_point(data, point_type, row[scope])
                        self.data.append(data_point)

                return 1
        except Exception as e:
            print(
                "problem parsing sheet {} for emissions in {}: {}".format(
                    sheet_name, report, e
                )
            )

        return 0

    def save_data(self):
        df = pd.DataFrame(self.data)

        outfile = join(settings.SCOTTISH_DIR, "extracted_data.csv")
        df.to_csv(open(outfile, "w"), index=False, header=True)

        return outfile
