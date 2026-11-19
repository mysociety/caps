import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand

from caps.import_utils import (
    add_authority_codes,
    add_gss_codes,
    get_google_sheet_export_as_csv,
)

# columns that are only for CE UK, or left over from the one-off conversion
# to one promise per row, so we don't import or publish them
UNUSED_COLUMNS = [
    "ceuk checked",
    "conversion source rows",
    "conversion flags",
]


def get_promises():
    get_google_sheet_export_as_csv(
        settings.PROMISES_CSV_KEY,
        settings.PROMISES_CSV,
        gid=settings.PROMISES_CSV_GID,
    )


class Command(BaseCommand):
    help = "fetch and import promises data"

    def handle(self, *args, **options):
        print("getting the promises csv")
        get_promises()
        df = pd.read_csv(settings.PROMISES_CSV, dtype=str, keep_default_na=False)
        df = df.drop(columns=UNUSED_COLUMNS, errors="ignore")
        # remove any rows with a blank council cell
        # seems to be loose ones at the end of the file
        df = df[df["council"].str.strip() != ""]
        df.to_csv(settings.PROMISES_CSV, index=False, header=True)
        print("adding council codes to promises")
        add_authority_codes(settings.PROMISES_CSV)
        add_gss_codes(settings.PROMISES_CSV)
