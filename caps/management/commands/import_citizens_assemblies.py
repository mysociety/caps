from mysoc_dataset import get_dataset_df
import requests

import pandas as pd

from caps.models import Council, PlanDocument
from pathlib import Path
from django.core.management.base import BaseCommand
from django.core.files import File
from django.conf import settings
from tqdm import tqdm
from datetime import datetime


def get_citizens_assembilies() -> pd.DataFrame:
    df = get_dataset_df(
        repo_name="citizen-assembly-data",
        package_name="citizens_assembly_register",
        file_name="register.csv",
        version_name="latest",
        done_survey=True,
    )

    # limit to those with 'climate' in the thematic_grouping
    df = df[df["thematic_grouping"].str.lower().str.contains("climate")]
    # limit to completed assemblies
    df = df[df["assembly_status"] == "Finished"]
    # limit to just those that have a local_authority_code
    df = df[df["local_authority_code"].notnull()]

    return df


class Command(BaseCommand):
    help = "Imports data from citizens assembles dataset at https://github.com/mysociety/citizen-assembly-data"

    changes = False

    def add_arguments(self, parser):
        parser.add_argument(
            "--all", action="store_true", help="Update all data not just previous"
        )
        parser.add_argument(
            "--redownload", action="store_true", help="Force redownload of files"
        )
        parser.add_argument(
            "--verbose", action="store_true", help="Print out more information"
        )

    def download_file(
        self, url: str, local_path: Path, *, verbose: bool = False
    ) -> None:
        if verbose:
            tqdm.write(f"Downloading {url} to {local_path}")
        response = requests.get(url, stream=True)
        response.raise_for_status()
        with local_path.open("wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)

    def handle(self, *args, **options):
        reprocess_all = options.get("all")
        verbose_output = options.get("verbose")
        redownload_files = options.get("redownload")

        council_lookup = dict(Council.objects.all().values_list("authority_code", "id"))

        if reprocess_all:
            if verbose_output:
                print("Deleting all existing citizens assembly documents")
            value = PlanDocument.objects.filter(
                document_type=PlanDocument.CITIZENS_ASSEMBLY
            ).delete()
            PlanDocument.history.filter(
                document_type=PlanDocument.CITIZENS_ASSEMBLY
            ).delete()
            if verbose_output:
                print(f"Deleted {value[0]} documents")

        # effectively tracking the unique_id of the assembly in the original dataset
        existing_assemblies = PlanDocument.objects.filter(
            document_type=PlanDocument.CITIZENS_ASSEMBLY
        ).values_list("url_hash", flat=True)

        data_path = Path(settings.MEDIA_ROOT, "data", "plans")

        df = get_citizens_assembilies()
        for _, assembly in tqdm(
            df.iterrows(), total=len(df), disable=not verbose_output
        ):
            destination_path = data_path / f"{assembly['unique_id']}.pdf"

            cached_pdf_url = assembly["cached_report_url"]
            hashed_url = PlanDocument.make_url_hash(cached_pdf_url)
            if hashed_url in existing_assemblies:
                continue
            if not destination_path.exists() or redownload_files:
                self.download_file(
                    cached_pdf_url, destination_path, verbose=verbose_output
                )

            # get file to be stored within the database
            document_file = destination_path.relative_to(settings.MEDIA_ROOT).open("rb")
            file_object = File(document_file)
            start_year = assembly["assembly_year"]
            today = datetime.now().date()
            PlanDocument(
                council_id=council_lookup[assembly["local_authority_code"]],
                start_year=start_year,
                date_first_found=today,
                file=file_object,
                url=assembly["report_pdf_url"],
                url_hash=hashed_url,
                document_type=PlanDocument.CITIZENS_ASSEMBLY,
                file_type="pdf",
                title=f"{start_year} Citizens Assembly report",
            ).save()
            document_file.close()
