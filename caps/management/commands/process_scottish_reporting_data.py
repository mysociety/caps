import re
from collections import defaultdict

from os.path import join

import pandas as pd
import numpy as np

from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = "processing scottish council climate data"

    data = defaultdict(list)

    report = None
    sheet = None
    sheet_name = None
    report_data = None
    data_type = None

    subsets = {
        "council_data": {
            "desc": "basic council data",
            "method": "extract_council_data_from_sheet",
        },
        "emissions": {
            "desc": "emissions data",
            "method": "extract_emissions_data_from_sheet",
            "header_text": "Baseline Year",
            "start_text": "Reference year",
        },
        "sources": {
            "desc": "emissions sources data",
            "method": "extract_emissions_sources_from_sheet",
            "header_text": "Emission source",
        },
        "targets": {
            "desc": "reduction targets data",
            "method": "extract_targets_from_sheet",
            "header_text": r"Name of [Tt]arget",
        },
        "projects": {
            "desc": "emission reduction projects data",
            "method": "extract_projects_from_sheet",
            "header_text": "Project name",
        },
        "generation": {
            "desc": "renewables generation data",
            "method": "extract_generation_from_sheet",
            "header_text": "Generation, consumption and export of renewable energy",
            "start_text": "Technology",
        },
    }

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            default=True,
            action="store_true",
            help="Update all data",
        )

        parser.add_argument(
            "--sample",
            action="store_true",
            help="Just process the first 20 rows for testing",
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
        df = pd.read_csv(data, nrows=20 if self.options["sample"] else None)

        for index, row in df.iterrows():
            try:
                self.report_data = row
                self.process_report()
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

            for name, args in self.subsets.items():
                self.data_type = name
                if (self.options["all"] or self.options[name]) and parsed.get(
                    name, 0
                ) != 1:
                    fetched = 0
                    method = getattr(self, args["method"])
                    if args.get("header_text", "") != "":
                        fetched = self.process_row_range(
                            name,
                            method,
                            args["header_text"],
                            args.get("start_text", None),
                        )
                    else:
                        fetched = method()

                    parsed[name] = fetched

    def make_data_point(self, point_type, point_data=None, **kwargs):
        data_point = {
            "council": self.report_data["council"],
            "authority_code": self.report_data["authority_code"],
            "start_year": self.report_data["start_year"],
            "end_year": self.report_data["end_year"],
            "data_type": point_type,
            **kwargs,
        }

        if point_data is not None:
            data_point["data_point"] = point_data

        self.data[self.data_type].append(data_point)

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
                        self.make_data_point("Budget", item)
                    elif (
                        type(last) is str
                        and last.find("full-time equivalent staff") > -1
                    ):
                        self.make_data_point("FTE", item)
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

    def process_row_range(self, name, processor, header_text, start_text=""):
        column = self.get_description_column()
        if column == -1:
            return 0

        try:
            df = self.get_row_range(column, header_text, start_text)
            if df is not None:
                return processor(df)
        except Exception as e:
            print(
                "problem parsing sheet {} for {} in {}: {}".format(
                    self.sheet_name, name, self.report, e
                )
            )

        return 0

    def extract_emissions_data_from_sheet(self, emissions_df):
        for index, row in emissions_df.iterrows():
            units = row["Units"]
            for scope in ["Scope 1", "Scope 2", "Scope 3"]:
                if pd.isna(row[scope]):
                    continue
                point_type = "scope emissions ({})".format(row["Year"])
                self.make_data_point(
                    point_type=point_type,
                    point_data=row[scope],
                    scope=scope,
                    units=units,
                )
            if not pd.isna(row["Total"]):
                point_type = "overall emissions ({})".format(row["Year"])
                self.make_data_point(
                    point_type=point_type, point_data=row["Total"], units=units
                )

        return 1

    def extract_emissions_sources_from_sheet(self, sources_df):
        for index, row in sources_df.iterrows():
            point_type = row["Emission source"]
            point_data = row["Emissions (tCO2e)"]
            if point_type in [
                "Please select from drop down box",
                "Other (please specify in comments)",
            ]:
                continue
            self.make_data_point(
                point_type="emissions source",
                point_data=point_data,
                sub_type=point_type,
                scope=row["Scope"],
                units="tCO2e",
            )

        return 1

    def extract_targets_from_sheet(self, targets_df):
        type_header = "Name of Target"
        if type_header not in targets_df.columns:
            type_header = "Name of target"

        for index, row in targets_df.iterrows():
            point_type = row[type_header]
            point_data = row["Target"]
            point_units = row["Units"]
            year = row["Target completion year"]
            if point_data in [
                "Please select from drop down box",
                "Other (please specify in comments)",
            ]:
                continue
            self.make_data_point(
                point_type="target",
                point_data=point_data,
                sub_type=point_type,
                units=point_units,
                target_year=year,
            )

        return 1

    def extract_projects_from_sheet(self, targets_df):
        """
        we don't replace the columns with our own as sadly they aren't always in the
        same order so instead we have to do some comparison to work out which column to use.
        Note that some of them are the same, only with spaces at the end.
        """
        measurement_columns = [
            "Are these savings figures estimated or actual? ",
            "Are these savings figures estimated or actual?",
            "Savings figures are estimated or actual ",
            "Savings figures are estimated or actual",
        ]

        valid_cols = [x for x in targets_df.columns if x in measurement_columns]
        assert len(valid_cols) == 1
        measurement = valid_cols[0]

        for col in [
            "Primary fuel/emission source saved",
            measurement,
            "First full year of CO2e savings",
        ]:
            targets_df[col] = targets_df[col].replace(
                "Please select from drop down box", ""
            )

        for index, row in targets_df.iterrows():
            project_name = row["Project name"].strip()
            emission_savings = row["Estimated carbon savings per year (tCO2e/annum)"]
            funding_source = row["Funding source"]
            if type(funding_source) == str:
                funding_source = funding_source.strip()
            self.make_data_point(
                point_type="project",
                emission_savings=emission_savings,
                project_name=project_name,
                lifetime=row["Project lifetime (years)"],
                cost=row["Capital cost (£)"],
                funding_source=funding_source,
                emission_source=row["Primary fuel/emission source saved"],
                annual_cost=row["Operational cost (£/annum)"],
                annual_savings=row["Estimated costs savings (£/annum)"],
                measurement=row[measurement],
                savings_start=row["First full year of CO2e savings"],
                comments=row["Comments"],
            )

        return 1

    def extract_generation_from_sheet(self, df):
        """
        The generation section uses merged cells in some templates so we need to handle different
        potential layouts for how this appears to pandas which we detect with columns count as
        pandas counts merged cells as a single column. The options are:

            Technology |  Renewable Energy   |   Renewable Heat
                       | consumed | exported | consumed | exported | comments
            or

            Technology | consumed | exported | consumed | exported | comments

        For the former that means we need to add one to the start_count to skip over the "headers"
        and then push technology in to the comments list as pandas sees the second row as having a
        blank header for the first column.

        There is also annoyance caused by having two columns with the same name which pandas copes
        with ok, but we need to fetch the non empty value out of them as only one of them is
        every populated.
        """
        col = self.get_description_column()
        titles = self.sheet.iloc[:, col]
        start_count = 0
        end_count = 0
        for index, item in titles.items():
            if (
                type(item) == str
                and re.match(self.subsets["generation"]["start_text"], item) is not None
            ):
                if len(df.columns) == 3:
                    start_count = index + 1
                else:
                    start_count = index
            if start_count > 0 and index > start_count and pd.isna(item):
                end_count = index
                break

        if end_count > start_count:
            row_range = self.sheet.iloc[start_count:end_count, col:]
            row_range = row_range.dropna(axis="columns", how="all")
            df = row_range.iloc[1:]

            columns = row_range.iloc[0, 1:].values
            columns = np.insert(columns, 0, "Technology")
            df.columns = columns

            consumed_col = None
            for name in [
                "Total consumed by the body (kWh)",
                "Total consumed by the organisation (kWh)",
            ]:
                if name in df.columns:
                    consumed_col = name
            if consumed_col is None:
                raise ValueError(
                    "consumed col is None, cols are: {}".format(df.columns)
                )

            data = {}

            for index, row in df.iterrows():
                if row["Technology"] == "Please select from drop down box":
                    break

                consumed = 0
                exported = 0
                # there are two columns for this in the spreadsheet for generation and heating but only
                # one ever has a value so use that. For our purposes we don't care about the nature of the
                # consumption, only the consumption
                for v in row[consumed_col].values:
                    if v > 0:
                        consumed = v
                for v in row["Total exported (kWh)"].values:
                    if v > 0:
                        exported = v

                self.make_data_point(
                    point_type="generation",
                    point_data=row["Technology"],
                    exported=exported,
                    consumed=consumed,
                    comments=row["Comments"],
                )

            return 1

    def save_data(self):
        for name, data in self.data.items():
            df = pd.DataFrame(data)

            outfile = join(settings.SCOTTISH_DIR, "{}_data.csv".format(name))
            df.to_csv(open(outfile, "w"), index=False, header=True)
