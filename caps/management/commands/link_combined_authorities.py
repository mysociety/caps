from django.core.management.base import BaseCommand, CommandError

from caps.import_utils import get_council_df
from caps.models import Council


class Command(BaseCommand):
    help = "Adds authority codes to the csv of plans"

    def link_combined_authorities(self):
        df = get_council_df()

        # limit just to those that have 'combined-authority'
        df = df[~df["combined-authority"].isna()]

        # iterate and link
        for _, row in df.iterrows():
            try:
                council = Council.objects.get(
                    authority_code=row["local-authority-code"]
                )
            except Council.DoesNotExist:
                self.stderr.write(f"Can't find council {row['nice-name']}")
            try:
                combined_authority = Council.objects.get(
                    authority_code=row["combined-authority"]
                )
            except Council.DoesNotExist:
                self.stderr.write(
                    f"Can't find combined authority {row['combined-authority']} for {row['nice-name']}"
                )
                continue

            council.combined_authority = combined_authority
            council.save()

    def handle(self, *args, **options):
        print("linking combined authorities")
        self.link_combined_authorities()
