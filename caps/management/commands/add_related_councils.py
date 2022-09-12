from pathlib import Path

import requests
from caps.models import (
    ComparisonLabel,
    ComparisonLabelAssignment,
    ComparisonType,
    Distance,
)
from django.core.management.base import BaseCommand, CommandError

from mysoc_dataset import get_dataset_url

SIMILARITY_TYPES = [
    "emissions_distance",
    "imd_distance",
    "physical_distance",
    "ruc_distance",
    "composite_distance",
]
SIMILARITY_FILES = [
    "distance_map.csv",
    "la_labels.csv",
    "label_desc.csv",
    "datapackage.json",
]
SIMILARITY_REPO = "local-authority-similarity"
SIMLARITY_VERSION = "1"


def download_data():
    """
    fetch the current version of the comparisons dataset
    """
    dst = Path("data", "comparisons")
    dst.mkdir(exist_ok=True)

    for type in SIMILARITY_TYPES:
        type_dst = dst / type
        type_dst.mkdir(exist_ok=True)
        for file in SIMILARITY_FILES:
            url = get_dataset_url(
                repo_name=SIMILARITY_REPO,
                package_name=type,
                version_name=SIMLARITY_VERSION,
                file_name=file,
                done_survey=True,
            )
            print(f"Downloading {url}")
            r = requests.get(url)
            if r.status_code != 200:
                raise CommandError(f"Failed to download {url}")
            with open(type_dst / file, "wb") as f:
                f.write(r.content)


def add_related_councils():
    ComparisonType.populate()
    ComparisonLabel.populate()
    ComparisonLabelAssignment.populate()
    Distance.populate()


class Command(BaseCommand):
    help = "Adds related authorities for each council using MapIt"

    def handle(self, *args, **options):
        get_all = options["all"]

        have_data = Path("data", "comparisons").exists()
        if get_all or have_data is False:
            print("downloading data")
            download_data()
            print("adding related authorities")
            add_related_councils()

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help="Update all data (slower but more thorough)",
        )
