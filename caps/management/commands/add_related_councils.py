import os
import tempfile
from zipfile import ZipFile
from pathlib import Path
from shutil import copytree
from io import BytesIO

import requests
from caps.models import (
    ComparisonLabel,
    ComparisonLabelAssignment,
    ComparisonType,
    Council,
    Distance,
)
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count

DISTANCE_VERSION = "1.0"
DISTANCE_REPO_ZIP = f"https://github.com/mysociety/la_distance/archive/refs/tags/v{DISTANCE_VERSION}.zip"


def download_data():
    """
    fetch the current version of the comparisons dataset
    """
    dst = Path("data", "comparisons")
    dst.mkdir(exist_ok=True)

    r = requests.get(DISTANCE_REPO_ZIP)
    z = ZipFile(BytesIO(r.content))

    with tempfile.TemporaryDirectory() as tmpdirname:
        z.extractall(tmpdirname)
        src = Path(tmpdirname, f"la_distance-{DISTANCE_VERSION}", "data", "outputs")
        copytree(src, dst, dirs_exist_ok=True)


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
