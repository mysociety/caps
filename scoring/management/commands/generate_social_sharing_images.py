import subprocess
from pathlib import Path

from caps.models import Council
from django.conf import settings
from django.core.management.base import BaseCommand
from django.urls import reverse_lazy
from scoring.models import PlanSection
from tqdm import tqdm


class Command(BaseCommand):
    help = "generate social sharing images for every council and section in the 2023 Scorecards"

    def add_arguments(self, parser):
        parser.add_argument(
            "baseurl",
            nargs="?",
            default="http://councilclimatescorecards.0.0.0.0.nip.io:8000",
            help="base url of site, eg: 'http://example.org'",
        )

    def get_shot(self, url, filepath):
        subprocess.run(
            [
                "shot-scraper",
                url,
                "--output",
                filepath,
                "--width",
                "1200",
                "--height",
                "630",
                "--silent",
            ]
        )

    def handle(self, *args, **options):
        og_images_dir = Path(settings.BASE_DIR, "og-img")

        # Create directory if it doesn’t already exist
        og_images_dir.mkdir(parents=True, exist_ok=True)

        # Create directories for each country/region
        for region in Council.REGION_CHOICES:
            Path(og_images_dir, region[0]).mkdir(parents=True, exist_ok=True)

        Path(og_images_dir, "sections").mkdir(parents=True, exist_ok=True)

        councils = Council.current_councils()
        sections = PlanSection.objects.filter(year=2023)

        tqdm.write(
            f"Generating open graph images for {councils.count()} councils into {og_images_dir}"
        )

        for council in tqdm(councils):
            url = "{}{}".format(
                options["baseurl"],
                reverse_lazy(
                    "scoring:council_preview",
                    urlconf="scoring.urls",
                    kwargs={"slug": council.slug},
                ),
            )
            filepath = Path(og_images_dir, council.region, f"{council.slug}.png")
            self.get_shot(url, filepath)

        tqdm.write(
            f"Generating open graph images for {sections.count()} sections into {og_images_dir}"
        )

        for section in tqdm(sections):
            for council_type in Council.SCORING_GROUPS.keys():
                url = "{}{}".format(
                    options["baseurl"],
                    reverse_lazy(
                        "scoring:section_preview",
                        urlconf="scoring.urls",
                        kwargs={"slug": section.code, "type": council_type},
                    ),
                )
                filepath = Path(
                    og_images_dir, section.description, f"{council_type}.png"
                )
                self.get_shot(url, filepath)
