import re
from collections import Counter
from typing import Optional

import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from caps.models import Council, Promise

"""
Wrap this in a transaction and delete all the things, as the sheet holds the
full history of every council's promises, so it makes more sense to just
remove and replace everything rather than try and work out what's changed.

Each row is one promise, one withdrawal of a promise, or (with a blank domain)
a council that was checked and found to have no promise.
"""

PROMISE_FIELDS = [
    "type",
    "status",
    "target date year",
    "target date text",
    "wording",
    "source url",
    "source name",
    "source date",
]


def choice_code(choices, label: str) -> Optional[int]:
    """
    Return the code for a choice label, ignoring case, or None if the label
    isn't one of the choices
    """
    labels_to_codes = {description.lower(): code for code, description in choices}
    return labels_to_codes.get(label.strip().lower())


def parse_year(value: str) -> Optional[int]:
    # years can come back from pandas as eg "2030.0"
    match = re.fullmatch(r"(\d{4})(\.0+)?", value.strip())
    if match:
        return int(match.group(1))
    return None


@transaction.atomic
def import_promises() -> tuple[Counter, list[str]]:
    """
    Import promises from settings.PROMISES_CSV, returning counts of what was
    imported and a list of warnings about rows that need checking
    """
    Promise.objects.all().delete()

    counts = Counter()
    warnings = []

    df = pd.read_csv(settings.PROMISES_CSV, dtype=str, keep_default_na=False)
    rows = [
        # +2 to match the row numbers in the sheet
        (index + 2, {column: value.strip() for column, value in row.items()})
        for index, row in df.iterrows()
    ]

    councils_with_promises = {row["council"] for _, row in rows if row["domain"]}

    def warn(row_number, row, message):
        warnings.append(f"Row {row_number} ({row['council']}): {message}")
        counts["skipped"] += 1

    for row_number, row in rows:
        if not row["gss_code"]:
            warn(row_number, row, "could not match council name to a GSS code")
            continue

        try:
            council = Council.objects.get(gss_code=row["gss_code"])
        except Council.DoesNotExist:
            warn(row_number, row, f"no council with GSS code {row['gss_code']}")
            continue

        if not row["domain"]:
            # a council that was checked, and found to have no promise
            if any(row[field] for field in PROMISE_FIELDS):
                warn(
                    row_number,
                    row,
                    "has a blank domain, but also has promise details",
                )
            elif not row["last checked"]:
                warn(row_number, row, "has a blank domain and no last checked date")
            elif row["council"] in councils_with_promises:
                warn(
                    row_number,
                    row,
                    "has a blank domain, but the council also has promises",
                )
            else:
                Promise.objects.create(
                    council=council,
                    has_promise=False,
                    last_checked=row["last checked"],
                    notes=row["notes"],
                )
                counts["no promise"] += 1
            continue

        codes = {
            "type": choice_code(Promise.TYPE_CHOICES, row["type"]),
            "status": choice_code(Promise.STATUS_CHOICES, row["status"]),
            "domain": choice_code(Promise.DOMAIN_CHOICES, row["domain"]),
            "scopes": choice_code(Promise.SCOPE_CHOICES, row["scopes"]),
        }
        unrecognised = [
            f"{column} '{row[column]}'"
            for column, code in codes.items()
            if code is None
        ]
        if unrecognised:
            warn(row_number, row, "unrecognised " + ", ".join(unrecognised))
            continue

        target_year = parse_year(row["target date year"])
        if row["target date year"] and target_year is None:
            warnings.append(
                f"Row {row_number} ({row['council']}): ignored target date year "
                f"'{row['target date year']}', which isn't a year"
            )
        if not row["source url"]:
            warnings.append(f"Row {row_number} ({row['council']}): no source url")

        Promise.objects.create(
            council=council,
            has_promise=True,
            type=codes["type"],
            status=codes["status"],
            domain=codes["domain"],
            scope=codes["scopes"],
            target_year=target_year,
            target_text=row["target date text"],
            text=row["wording"],
            source=row["source url"],
            source_name=row["source name"],
            source_date=row["source date"],
            last_checked=row["last checked"],
            notes=row["notes"],
        )
        counts[f"{row['type'].lower()} ({row['status'].lower()})"] += 1

    return counts, warnings


class Command(BaseCommand):
    help = "import promises data"

    def handle(self, *args, **options):
        counts, warnings = import_promises()

        for warning in warnings:
            self.stderr.write(warning)

        for label, count in sorted(counts.items()):
            self.stdout.write(f"{label}: {count}")
