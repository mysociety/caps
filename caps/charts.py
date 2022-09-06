from typing import TYPE_CHECKING

from .models import Council, DataPoint

import altair as alt
import pandas as pd
from charting import ChartBundle


def multi_emissions_chart(council: Council, year: int):

    # get just the total emissions data
    totals = [
        "Industry Total",
        "Commercial Total",
        "Public Sector Total",
        "Transport Total",
        "Domestic Total",
        "Agriculture Total",
    ]

    df = DataPoint.objects.filter(
        council=council, data_type__name_in_source__in=totals
    ).to_dataframe("year", ("data_type__name_in_source", "emissions_type"), "value")

    # get row percentages
    pdf = df.pivot_table("value", index="year", columns="emissions_type", aggfunc="sum")
    pdf = (
        pdf.div(pdf.sum(axis=1), axis=0)
        .reset_index()
        .melt(id_vars=["year"])
        .rename(columns={"value": "row_percentage"})
    )
    df = df.merge(pdf)

    # Tidy Emissions type label
    df["emissions_type"] = df["emissions_type"].str.replace(" Total", "")

    # altair doesn't pick up years right unless in a fake date format
    df["Year"] = df["year"]
    df["year"] = df["year"].astype(int).apply(lambda x: f"{x}-01-01")

    chart = (
        alt.Chart(df)
        .mark_area()
        .encode(
            x=alt.X("year:T", title="", axis=alt.Axis(labelAlign="center")),
            y=alt.Y(
                "value",
                title="",
            ),
            color=alt.Color(
                "emissions_type",
                scale=alt.Scale(
                    domain=[
                        "Commercial",
                        "Domestic",
                        "Industry",
                        "Public Sector",
                        "Transport",
                        "Agriculture",
                    ],
                    range=[
                        "#00aeee",  # $color-ceuk-blue
                        "#005cab",  # $color-ceuk-navy
                        "#e11d21",  # $color-ceuk-red
                        "#f29e1a",  # $color-ceuk-orange
                        "#ffd80b",  # $color-ceuk-yellow
                        "#D4C2FC",  # $color-ceuk-purple
                    ],
                ),
            ),
            tooltip=[
                "Year",
                alt.Tooltip("emissions_type", title="Type"),
                alt.Tooltip("value", title="Emissions in ktCO2e", format=",.2f"),
                alt.Tooltip(
                    "row_percentage", title="% of Emissions in year", format=".1%"
                ),
            ],
        )
        .properties(
            title=alt.TitleParams(
                f"Historic emissions by sector, 2005–{year}",
                subtitle=[f"{council.name}, ktCO2e"],
            ),
            width="container",
            height=300,
        )
    )

    # wide format table for longdesc
    wide_table = (
        df.rename(columns={"emissions_type": "Emissions Type"})
        .pivot_table(
            ["value"],
            index="Year",
            columns="Emissions Type",
            aggfunc="sum",
        )
        .style.format("{:.2f}".format)
    )

    alt_title = f"Chart showing emissions by sector for {council.name}"
    data_source = "Data source: 2020 BEIS Emissions data"

    return ChartBundle(
        label="multi_emissions",
        df=wide_table,
        chart=chart,
        alt_title=alt_title,
        data_source=data_source,
    )
