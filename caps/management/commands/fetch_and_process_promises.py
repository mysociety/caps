from django.core.management.base import BaseCommand
from django.conf import settings

from caps.import_utils import (
    add_authority_codes,
    add_gss_codes,
    get_google_sheet_as_csv,
    replace_csv_headers,
)


def get_promises():
    get_google_sheet_as_csv(
        settings.PROMISES_CSV_KEY,
        settings.PROMISES_CSV,
        sheet_name=settings.PROMISES_CSV_SHEET_NAME,
    )


# Replace the column header lines
def replace_headers():
    replace_csv_headers(
        settings.PROMISES_CSV,
        [
            "council",
            "scope",
            "target",
            "wording",
            "source_url",
            "source_name",
            "notes",
        ],
    )


class Command(BaseCommand):
    help = "fetch and import promises data"

    def handle(self, *args, **options):
        print("getting the promises csv")
        get_promises()
        print("replacing promises headers")
        replace_headers()
        print("adding council codes to promises")
        add_authority_codes(settings.PROMISES_CSV)
        add_gss_codes(settings.PROMISES_CSV)
