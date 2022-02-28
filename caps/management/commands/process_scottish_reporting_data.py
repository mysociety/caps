import re

from os.path import join

import pandas as pd

from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = "processing scottish council climate data"

    data = []

    report = None
    sheet = None
    sheet_name = None
    report_data = None

    subsets = {
        "council_data": "basic council data",
        "emissions": "emissions data",
        "sources": "emissions sources data",
    }

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            default=True,
            action="store_true",
            help="Update all data",
        )

        for arg, desc in self.subsets.items():
            parser.add_argument(
                "--{}".format(arg),
                action="store_true",
                help="Update {}".format(desc),
            )

    def handle(self, *args, **options):
        self.options = options

        get_all = options["all"]
        for option in self.subsets.keys():
            if options[option]:
                self.options["all"] = False
                break

        self.process_data()
        self.save_data()

    def process_data(self):
        data = join(settings.SCOTTISH_DIR, "data_list.csv")
        df = pd.read_csv(data)

        for index, row in df.iterrows():
            try:
                self.report_data = row
                self.process_report()
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

        self.report = join(settings.SCOTTISH_DIR, self.report_data["file"])

        xls = pd.ExcelFile(self.report)
        parsed = {}
        for sheet_name in xls.sheet_names:
            self.sheet_name = sheet_name
            # skip this as it's a title page
            if sheet_name == "Guide":
                continue

            try:
                self.sheet = pd.read_excel(self.report, sheet_name)
            except Exception as e:
                print(
                    "problem reading sheet {} for council data in {}: {}".format(
                        sheet_name, self.report, e
                    )
                )
                return

            if (self.options["all"] or self.options["council_data"]) and parsed.get(
                "council", 0
            ) != 1:
                fetched = self.extract_council_data_from_sheet()
                parsed["council"] = fetched

            if (self.options["all"] or self.options["emissions"]) and parsed.get(
                "emissions", 0
            ) != 1:
                fetched = self.extract_emissions_data_from_sheet()
                parsed["emissions"] = fetched

            if (self.options["all"] or self.options["sources"]) and parsed.get(
                "sources", 0
            ) != 1:
                fetched = self.extract_emissions_sources_from_sheet()
                parsed["sources"] = fetched

    def make_data_point(self, point_type, point_value, sub_type="", units="", scope=""):
        data_point = {
            "council": self.report_data["council"],
            "authority_code": self.report_data["authority_code"],
            "start_year": self.report_data["start_year"],
            "end_year": self.report_data["end_year"],
            "data_type": point_type,
            "sub_type": sub_type,
            "data_value": point_value,
            "units": units,
            "scope": scope,
        }

        return data_point

    def get_description_column(self):
        column = 1

        # doesn't hold any useful data and just generated warnings
        if self.report_data["start_year"] == 2014 and self.sheet_name == "Sheet2":
            column = -1

        if self.report_data["start_year"] >= 2020:
            column = 2

        if len(self.sheet.columns) <= column:
            column = -1

        return column

    def extract_council_data_from_sheet(self):
        column = self.get_description_column()
        if column == -1:
            return 0

        try:
            titles = self.sheet.iloc[:, column]
            if titles.str.contains(
                r"Name of (?:the organisation|reporting body)"
            ).any():
                last = ""
                for item in titles:
                    if last == "Budget":
                        data_point = self.make_data_point("Budget", item)
                        self.data.append(data_point)
                    elif (
                        type(last) is str
                        and last.find("full-time equivalent staff") > -1
                    ):
                        data_point = self.make_data_point("FTE", item)
                        self.data.append(data_point)
                    last = item
                return 1
        except Exception as e:
            print(
                "problem parsing sheet {} for council data in {}: {}".format(
                    self.sheet_name, self.report, e
                )
            )

        return 0

    def get_row_range(self, column, header_text, start_text=None):
        if start_text is None:
            start_text = header_text

        titles = self.sheet.iloc[:, column]
        df = None
        if titles.str.contains(header_text).any():
            start_count = 0
            end_count = 0
            for index, item in titles.items():
                if type(item) == str and re.match(start_text, item) is not None:
                    start_count = index
                if start_count > 0 and pd.isna(item):
                    end_count = index
                    break

            if end_count > start_count:
                row_range = self.sheet.iloc[start_count:end_count, column:]
                row_range = row_range.dropna(axis="columns", how="all")
                df = row_range.iloc[1:]
                df.columns = row_range.iloc[0].values

        return df

    def extract_emissions_data_from_sheet(self):
        column = self.get_description_column()
        if column == -1:
            return 0

        try:
            emissions_df = self.get_row_range(column, "Baseline Year", "Reference year")
            if emissions_df is not None:
                for index, row in emissions_df.iterrows():
                    units = row["Units"]
                    for scope in ["Scope 1", "Scope 2", "Scope 3"]:
                        if pd.isna(row[scope]):
                            continue
                        point_type = "scope emissions ({})".format(row["Year"])
                        data_point = self.make_data_point(
                            point_type, row[scope], scope=scope, units=units
                        )
                        self.data.append(data_point)
                    if not pd.isna(row["Total"]):
                        point_type = "overall emissions ({})".format(row["Year"])
                        data_point = self.make_data_point(
                            point_type, row["Total"], units=units
                        )
                        self.data.append(data_point)

                return 1
        except Exception as e:
            print(
                "problem parsing sheet {} for emissions in {}: {}".format(
                    self.sheet_name, self.report, e
                )
            )

        return 0

    def extract_emissions_sources_from_sheet(self):
        column = self.get_description_column()
        if column == -1:
            return 0

        try:
            sources_df = self.get_row_range(column, "Emission source")
            if sources_df is not None:
                for index, row in sources_df.iterrows():
                    point_type = row["Emission source"]
                    point_data = row["Emissions (tCO2e)"]
                    if point_type in [
                        "Please select from drop down box",
                        "Other (please specify in comments)",
                    ]:
                        continue
                    data_point = self.make_data_point(
                        "emissions source",
                        point_data,
                        sub_type=point_type,
                        scope=row["Scope"],
                        units="tCO2e",
                    )
                    self.data.append(data_point)

                return 1
        except Exception as e:
            print(
                "problem parsing sheet {} for emissions in {}: {}".format(
                    self.sheet_name, self.report, e
                )
            )

        return 0

    def save_data(self):
        df = pd.DataFrame(self.data)

        outfile = join(settings.SCOTTISH_DIR, "extracted_data.csv")
        df.to_csv(open(outfile, "w"), index=False, header=True)

        return outfile
