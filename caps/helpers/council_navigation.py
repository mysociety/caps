from typing import NamedTuple


class MenuItem(NamedTuple):
    """
    Helper object to track valid council cards
    """

    slug: str
    title: str
    color: str = "green"
    desc: str = ""
    list_in_summary: bool = True


# new additions here also need to be made to content-navbar.scss

council_menu = [
    MenuItem(
        slug="summary",
        title="Summary",
        color="blue",
        desc="Overview of CAPE and the information available.",
        list_in_summary=False,
    ),
    MenuItem(
        slug="new-council",
        title="What did this council replace?",
        color="red",
        desc="Details of councils this authority replaced.",
        list_in_summary=False,
    ),
    MenuItem(
        slug="old-council",
        title="What replaced this council?",
        color="red",
        desc="Details of councils that replaced this authority.",
        list_in_summary=False,
    ),
    MenuItem(
        slug="powers",
        title="Powers & responsibilities",
        color="green",
        desc="What the council is responsible for and how it relates to climate change.",
    ),
    MenuItem(
        slug="declarations",
        title="Declarations & pledges",
        color="cyan",
        desc="Declarations & pledges the council has made around climate change.",
    ),
    MenuItem(
        slug="climate-documents",
        title="Climate documents",
        desc="Documents, Reports and Plans this council has released related to its climate change plans.",
    ),
    MenuItem(
        slug="scorecard",
        title="Council Climate Scorecard",
        color="green",
        desc="How this council's plans scored on CEUK's 2021 Scorecards.",
    ),
    MenuItem(
        slug="emissions",
        title="Emissions data",
        color="blue",
        desc="The emissions profile and history for this council.",
    ),
    MenuItem(
        slug="emissions-reduction-projects",
        title="Emissions reduction projects",
        color="blue",
        desc="Projects this council has undertaken to reduce emissions.",
    ),
    MenuItem(
        slug="climate-assembly",
        title="Climate assembly",
        color="cyan",
        desc="Information about any climate assembly held by this council.",
    ),
    MenuItem(
        slug="local-polling",
        title="Local polling",
        color="cyan",
        desc="MRP Polling of climate change attitudes for this council area.",
    ),
    MenuItem(
        slug="related-councils",
        title="Related councils",
        color="blue",
        desc="Lists of councils with similar characteristics to this council.",
    ),
    MenuItem(
        slug="other-resources",
        title="Other resources",
        color="cyan",
        desc="Links to other resources and information about this council.",
        list_in_summary=False,
    ),
    MenuItem(
        slug="download-data",
        title="Download our data",
        color="red",
        desc="How to download the information we hold on UK councils",
        list_in_summary=False,
    ),
    MenuItem(
        slug="cite",
        title="Cite this page",
        color="blue",
        desc="How to cite or credit infomation on this site",
        list_in_summary=False,
    ),
    MenuItem(
        slug="improve",
        title="Help us improve",
        color="green",
        desc="Give us feedback on if you found this site useful.",
        list_in_summary=False,
    ),
]
