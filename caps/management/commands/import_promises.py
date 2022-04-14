import re
import sys
import pandas as pd

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import transaction

from caps.models import Council, PlanDocument, Promise
from caps.import_utils import add_authority_codes, add_gss_codes
from caps.utils import char_from_text

"""
Wrap this in a transaction and delete all the things as it makes more sense
to just remove and replace everything rather than try and work out what's
changed as we only care about the now.
"""


@transaction.atomic
def import_promises():
    # just refresh everything
    Promise.objects.all().delete()

    df = pd.read_csv(settings.PROMISES_CSV)
    for index, row in df.iterrows():
        scope = row["scope"]
        gss_code = row["gss_code"]
        if pd.isnull(row["gss_code"]) or gss_code == "nan":
            continue

        try:
            council = Council.objects.get(gss_code=gss_code)
        except Council.DoesNotExist:
            print(
                "Could not find council to import promise: %s" % row["council"],
                file=sys.stderr,
            )
            continue

        if not pd.isnull(row["source_url"]):

            if scope == "Council operations":
                scope = "Council only"

            target_year = None
            non_numbers = re.compile(r"^(\d{4}).*$")
            # needs to be a string for the regexp to work
            target = str(char_from_text(row["target"]))

            # some of the entries in the sheet are not years or have slight
            # clarifications so remove those
            target = non_numbers.sub(r"\1", target)
            if len(target) == 4:
                target_year = target

            promise = Promise.objects.create(
                council=council,
                scope=PlanDocument.scope_code(scope),
                source=char_from_text(row["source_url"]),
                source_name=char_from_text(row["source_name"]),
                target_year=target_year,
                text=char_from_text(row["wording"]),
                notes=char_from_text(row["notes"]),
                has_promise=True,
            )

        elif scope == "No promise":
            promise = Promise.objects.create(
                council=council, scope=PlanDocument.scope_code(scope), has_promise=False
            )


class Command(BaseCommand):
    help = "fetch and import promises data"

    def handle(self, *args, **options):
        import_promises()
