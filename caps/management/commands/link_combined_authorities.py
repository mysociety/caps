from caps.models import Council
from django.core.management.base import BaseCommand, CommandError

from caps.import_utils import get_council_df


def link_combined_authorities():
    df = get_council_df()

    # limit just to those that have 'combined-authority'
    df = df[~df["combined-authority"].isna()]

    # iterate and link
    for _, row in df.iterrows():
        council = Council.objects.get(authority_code=row["local-authority-code"])
        combined_authority = Council.objects.get(
            authority_code=row["combined-authority"]
        )
        council.combined_authority = combined_authority
        council.save()


class Command(BaseCommand):
    help = "Adds authority codes to the csv of plans"

    def handle(self, *args, **options):
        print("linking combined authorities")
        link_combined_authorities()
