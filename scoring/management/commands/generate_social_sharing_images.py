import subprocess
from pathlib import Path
from shutil import copyfile

from django.conf import settings
from django.core.management.base import BaseCommand
from django.urls import reverse_lazy
from tqdm import tqdm

from caps.models import Council
from scoring.models import PlanScore, PlanSection, PlanSectionScore


class Command(BaseCommand):
    help = "generate social sharing images for every council and section in the 2023 Scorecards"

    def add_arguments(self, parser):
        parser.add_argument(
            "baseurl",
            nargs="?",
            default="http://councilclimatescorecards.0.0.0.0.nip.io:8000",
            help="base url of site, eg: 'http://example.org'",
        )
        parser.add_argument(
            "--top_performers_only",
            action="store_true",
            help="Only generate graphics for top performers",
        )

    def get_shot(self, url, filepath, width=1200, height=630):
        subprocess.run(
            [
                "shot-scraper",
                url,
                "--output",
                filepath,
                "--width",
                f"{width}",
                "--height",
                f"{height}",
                "--silent",
            ]
        )

    def handle(self, *args, **options):
        top_performers = options["top_performers_only"]

        og_images_dir = Path(settings.BASE_DIR, "social-images")
        static_images_dir = Path(
            settings.BASE_DIR, "scoring/static/scoring/img/og-images/"
        )

        og_images_dir.mkdir(parents=True, exist_ok=True)
        static_images_dir.mkdir(parents=True, exist_ok=True)

        councils = Council.current_councils()
        sections = PlanSection.objects.filter(year=2023)

        if top_performers:
            overall = list(
                PlanScore.objects.filter(year=2023)
                .exclude(top_performer="")
                .values_list("council_id", flat=True)
            )

            section = list(
                PlanSectionScore.objects.filter(plan_section__in=sections)
                .exclude(top_performer="")
                .values_list("plan_score__council_id", flat=True)
            )

            top_performer_list = overall + section

            councils = councils.filter(id__in=top_performer_list)

        sizes = [
            (1200, 630),
            (1000, 1000),
        ]

        for size in sizes:
            size_by = f"{size[0]}x{size[1]}"

            tqdm.write(
                f"Generating {size_by} images for {councils.count()} councils into {og_images_dir}/{size_by}/councils"
            )

            for council in tqdm(councils, leave=False):
                url = "{}{}".format(
                    options["baseurl"],
                    reverse_lazy(
                        "scoring:council_preview",
                        urlconf="scoring.urls",
                        kwargs={"slug": council.slug},
                    ),
                )
                dirpath = Path(
                    og_images_dir,
                    size_by,
                    "councils",
                    council.region,
                )
                dirpath.mkdir(parents=True, exist_ok=True)

                filepath = Path(
                    dirpath,
                    f"{council.slug}.png",
                )
                self.get_shot(url, filepath, width=size[0], height=size[1])

                if size == (1200, 630):
                    og_path = Path(static_images_dir, f"{council.slug}.png")
                    copyfile(filepath, og_path)

            tqdm.write(
                f"Generating {size_by} images for {sections.count()} sections into {og_images_dir}/{size_by}/sections"
            )

            for section in tqdm(sections, position=0, leave=False):
                for council_type in tqdm(
                    Council.SCORING_GROUPS.keys(), position=1, leave=False
                ):
                    url = "{}{}".format(
                        options["baseurl"],
                        reverse_lazy(
                            "scoring:section_preview",
                            urlconf="scoring.urls",
                            kwargs={"slug": section.code, "type": council_type},
                        ),
                    )
                    filepath = Path(
                        og_images_dir,
                        size_by,
                        "sections",
                        section.description,
                        f"{council_type}.png",
                    )
                    self.get_shot(url, filepath, width=size[0], height=size[1])

                dirpath = Path(
                    og_images_dir,
                    size_by,
                    "sections",
                    section.description,
                    "top_performers",
                )
                dirpath.mkdir(parents=True, exist_ok=True)
                performers = PlanSectionScore.objects.filter(
                    plan_section=section
                ).exclude(top_performer="")
                for performer in performers:
                    url = "{}{}".format(
                        options["baseurl"],
                        reverse_lazy(
                            "scoring:section_top_council_preview",
                            urlconf="scoring.urls",
                            kwargs={
                                "slug": performer.plan_section.code,
                                "council": performer.plan_score.council.slug,
                            },
                        ),
                    )
                    filepath = Path(
                        dirpath,
                        f"{performer.plan_score.council.slug}.png",
                    )
                    self.get_shot(url, filepath, width=size[0], height=size[1])

                url = "{}{}".format(
                    options["baseurl"],
                    reverse_lazy(
                        "scoring:section_top_preview",
                        urlconf="scoring.urls",
                        kwargs={"slug": section.code},
                    ),
                )
                dirpath = Path(
                    og_images_dir,
                    size_by,
                    "sections",
                    section.description,
                )
                dirpath.mkdir(parents=True, exist_ok=True)

                filepath = Path(
                    dirpath,
                    "top_performer.png",
                )
                self.get_shot(url, filepath, width=size[0], height=size[1])

            tqdm.write(
                f"Generating {size_by} images for top performing council of each type into {og_images_dir}/{size_by}/top_performers"
            )

            for council_type in tqdm(Council.SCORING_GROUPS.keys(), leave=False):
                url = "{}{}".format(
                    options["baseurl"],
                    reverse_lazy(
                        "scoring:council_type_top_preview",
                        urlconf="scoring.urls",
                        kwargs={"council_type": council_type},
                    ),
                )
                dirpath = Path(og_images_dir, size_by, "top_performers")
                dirpath.mkdir(parents=True, exist_ok=True)
                filepath = Path(dirpath, f"{council_type}.png")
                self.get_shot(url, filepath, width=size[0], height=size[1])
