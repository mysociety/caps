"""
One-off conversion of CEUK's 2026 "updated net zero targets" spreadsheet into
a simpler format, with one promise per row.

The 2026 sheet has the original promise in columns C-G, and CEUK's update to
that promise in columns H-O, side by side. This command splits each of those
rows into the original promise (marked as superseded or withdrawn, if it has
been) and the new promise(s) that replaced it, so that the output can be
pasted into a new tab of the Google Sheet, checked by CEUK, and imported
without needing to reinterpret the side-by-side structure on every import.

Councils which aren't in the 2026 sheet at all (mostly councils abolished in
local government reorganisations) have their promises copied over from the
"Original Net zero targets" tab, so that their data isn't lost.

Anything that the conversion couldn't do confidently is described in the
conversion_flags column, for a human to review.

Both tabs are fetched directly from the Google Sheet as CSV, so cells arrive
as the text displayed in the sheet (eg dates as "Dec 2024", not 2024-12-01).
"""

import csv
import datetime
import re
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from caps.import_utils import get_authority_mapping, get_google_sheet_export_as_csv

# Statuses used by CEUK in the "Confirmed still accurate?" column
STILL_CURRENT = "target still current"
WRONG_INITIALLY = "wrong initially - target still current"
UPDATED_STRONGER = "updated target - stronger"
UPDATED_WEAKER = "updated target - weaker"
NEW_TARGET = "new target"
NEW_AUTHORITY = "new authority - new target"
WITHDRAWN = "withdrawn"
TARGET_MISSED = "target missed - no further target set"
TARGET_MET = "target met"
NO_PROMISE = "no promise"

# Values used in the output
COUNCIL_OPERATIONS = "Council operations"
WHOLE_AREA = "Whole area"
UNCLEAR = "Unclear"

NOT_SPECIFIED = "Not specified"
SCOPES_1_2_3 = "Scopes 1, 2 & 3"
SCOPES_1_2 = "Scopes 1 & 2"
SCOPE_3 = "Scope 3"

LATEST = "Latest"
SUPERSEDED = "Superseded"
STATUS_WITHDRAWN = "Withdrawn"

TYPE_PROMISE = "Promise"
TYPE_WITHDRAWAL = "Withdrawal"

# Values found in CEUK's scope columns, mapped to (domain, scopes) pairs.
# Matched case insensitively.
SCOPE_VALUES = {
    "council operations": [(COUNCIL_OPERATIONS, NOT_SPECIFIED)],
    "whole area": [(WHOLE_AREA, NOT_SPECIFIED)],
    "unclear": [(UNCLEAR, NOT_SPECIFIED)],
    "council operations - scope 1 & 2": [(COUNCIL_OPERATIONS, SCOPES_1_2)],
    "council operations - scope 3": [(COUNCIL_OPERATIONS, SCOPE_3)],
    "whole area (scope 1 and 2)": [(WHOLE_AREA, SCOPES_1_2)],
    "council operations and whole area": [
        (COUNCIL_OPERATIONS, NOT_SPECIFIED),
        (WHOLE_AREA, NOT_SPECIFIED),
    ],
}

OUTPUT_COLUMNS = [
    "council",
    "last_checked",
    "type",
    "status",
    "domain",
    "scopes",
    "target_date_year",
    "target_date_text",
    "wording",
    "source_url",
    "source_name",
    "source_date",
    "notes",
    "ceuk_review_outcome",
    "ceuk_checked",
    "conversion_source_rows",
    "conversion_flags",
]

# Columns in the 2026 sheet, found by the start of their header text, so
# that the command still works if CEUK add or move columns.
UPDATED_SHEET_COLUMNS = {
    "checked": "checked?",
    "council": "council",
    "scope": "scope",
    "target": "target year",
    "wording": "exact wording",
    "source_url": "source url",
    "source_name": "source name",
    "status": "confirmed still accurate?",
    "new_scope": "scope (only for new targets",
    "new_target": "new target year",
    "new_wording": "copy and paste exact wording",
    "new_source_url": "new target source url",
    "new_source_name": "new source name",
    "new_source_date": "updated source date",
    "notes": "notes",
}

ORIGINAL_SHEET_COLUMNS = {
    "council": "council",
    "scope": "scope",
    "target": "target year",
    "wording": "exact wording",
    "source_url": "source url",
    "source_name": "source name",
    "notes": "notes",
}

MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
MONTH_PATTERN = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"

# Date formats found in the "Updated Source Date" column, and the names of
# their groups. Matched against the lowercased cell text.
DATE_PATTERNS = [
    # eg "Wednesday, 2nd November, 2022", "12th November 2025", "29 April 26"
    (
        r"(?:[a-z]+day,?\s+)?(\d{1,2})(?:st|nd|rd|th)?\s+"
        + MONTH_PATTERN
        + r",?\s+(\d{4}|\d{2})",
        ("day", "month", "year"),
    ),
    # eg "16/07/2025"
    (r"(\d{1,2})/(\d{1,2})/(\d{4})", ("day", "month", "year")),
    # eg "2025-07-16"
    (r"(\d{4})-(\d{1,2})-(\d{1,2})", ("year", "month", "day")),
    # eg "Sept 2022", "September 2025"
    (MONTH_PATTERN + r",?\s+(\d{4}|\d{2})", ("month", "year")),
    # eg "07/2025"
    (r"(\d{1,2})/(\d{4})", ("month", "year")),
    # eg "2025-7"
    (r"(\d{4})-(\d{1,2})", ("year", "month")),
]

STATUS_ORDER = {STATUS_WITHDRAWN: 0, SUPERSEDED: 0, LATEST: 1, "": 2}
DOMAIN_ORDER = {COUNCIL_OPERATIONS: 0, WHOLE_AREA: 1, UNCLEAR: 2, "": 3}
SCOPES_ORDER = {NOT_SPECIFIED: 0, SCOPES_1_2_3: 1, SCOPES_1_2: 2, SCOPE_3: 3, "": 4}


@dataclass
class Promise:
    council: str
    last_checked: str = ""
    type: str = ""
    domain: str = ""
    scopes: str = ""
    target_date_year: Optional[int] = None
    target_date_text: str = ""
    status: str = ""
    wording: str = ""
    source_url: str = ""
    source_name: str = ""
    source_date: str = ""
    notes: str = ""
    ceuk_review_outcome: str = ""
    ceuk_checked: str = ""
    source_rows: list = field(default_factory=list)
    flags: list = field(default_factory=list)

    def flag(self, message: str):
        if message not in self.flags:
            self.flags.append(message)

    def add_note(self, note: str):
        self.notes = join_text(self.notes, note)

    def same_target(self, other: "Promise") -> bool:
        return (
            self.type,
            self.domain,
            self.scopes,
            self.target_date_year,
            self.target_date_text,
            self.status,
        ) == (
            other.type,
            other.domain,
            other.scopes,
            other.target_date_year,
            other.target_date_text,
            other.status,
        )

    def same_source(self, other: "Promise") -> bool:
        return (self.wording, self.source_url) == (other.wording, other.source_url)

    def merge(self, other: "Promise"):
        """
        Merge a duplicate promise into this one
        """
        for row in other.source_rows:
            if row not in self.source_rows:
                self.source_rows.append(row)
        if other.notes not in self.notes:
            self.notes = join_text(self.notes, other.notes)
        if other.ceuk_review_outcome not in self.ceuk_review_outcome:
            self.ceuk_review_outcome = join_text(
                self.ceuk_review_outcome, other.ceuk_review_outcome, "; "
            )
        for message in other.flags:
            self.flag(message)

    def describe(self) -> str:
        target = self.target_date_year or self.target_date_text or "no target date"
        parts = [self.domain or "no domain"]
        if self.scopes and self.scopes != NOT_SPECIFIED:
            parts.append(self.scopes)
        parts.append(str(target))
        if self.source_url:
            parts.append(self.source_url)
        return ", ".join(parts)

    def sort_key(self):
        return (
            self.council.casefold(),
            STATUS_ORDER.get(self.status, 9),
            DOMAIN_ORDER.get(self.domain, 9),
            SCOPES_ORDER.get(self.scopes, 9),
            self.target_date_year or 9999,
            self.source_rows,
        )

    def as_row(self) -> dict:
        row = {col: getattr(self, col, "") for col in OUTPUT_COLUMNS}
        row["target_date_year"] = self.target_date_year or ""
        row["conversion_source_rows"] = ", ".join(self.source_rows)
        row["conversion_flags"] = "\n".join(self.flags)
        return row


def join_text(first: str, second: str, separator: str = "\n\n") -> str:
    return separator.join(text for text in [first, second] if text)


def clean(value) -> str:
    """
    Return a cell value as a stripped string, or an empty string if blank
    """
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()


def clean_notes(value) -> str:
    # the original sheet uses "No notes" as a placeholder
    notes = clean(value)
    return "" if notes.lower() == "no notes" else notes


def parse_scope(value) -> Optional[list[tuple[str, str]]]:
    """
    Return a list of (domain, scopes) pairs for a CEUK scope value, or None if
    it isn't one we recognise.
    """
    return SCOPE_VALUES.get(clean(value).lower())


def looks_like_year(value) -> bool:
    return bool(re.fullmatch(r"(19|20)\d\d", clean(value)))


def parse_target(value) -> tuple[Optional[int], str, Optional[str]]:
    """
    Return (year, text, flag) for a target date cell
    """
    text = clean(value)
    if not text:
        return None, "", None
    if looks_like_year(text):
        return int(text), "", None
    if text == "?":
        return None, "", "Target date was '?'"
    return None, text, f"Target date isn't a plain year: '{text}'"


def full_year(year: str) -> int:
    # two digit years, eg "29 April 26"
    return int(year) + 2000 if len(year) == 2 else int(year)


def format_date(value) -> tuple[str, Optional[str]]:
    """
    Return (date, flag) for a date cell, formatted as YYYY, YYYY-MM or
    YYYY-MM-DD depending on how precise the original value was.
    """
    text = clean(value)
    if not text:
        return "", None
    if looks_like_year(text):
        return text, None

    for pattern, group_names in DATE_PATTERNS:
        match = re.fullmatch(pattern, text.lower())
        if not match:
            continue
        parts = dict(zip(group_names, match.groups()))
        year = full_year(parts["year"])
        month = MONTHS.get(parts["month"]) or int(parts["month"])
        try:
            if "day" in parts:
                date = datetime.date(year, month, int(parts["day"]))
                return date.strftime("%Y-%m-%d"), None
            date = datetime.date(year, month, 1)
            return date.strftime("%Y-%m"), None
        except ValueError:
            break

    return text, f"Couldn't standardise date: '{text}'"


def looks_like_url(value: str) -> bool:
    return bool(re.match(r"https?://", value))


def find_columns(header_row, wanted: dict[str, str], sheet_name: str) -> dict:
    """
    Return a dict of column name to column index, matching headers by prefix
    """
    headers = [clean(header).lower() for header in header_row]
    columns = {}
    for name, prefix in wanted.items():
        # prefer an exact match, so "scope" doesn't match "scope (only for..."
        matches = [i for i, header in enumerate(headers) if header == prefix]
        if not matches:
            matches = [
                i for i, header in enumerate(headers) if header.startswith(prefix)
            ]
        if not matches:
            raise CommandError(
                f"Couldn't find a '{prefix}' column in the '{sheet_name}' sheet"
            )
        columns[name] = matches[0]
    return columns


def fetch_sheet(key: str, gid: str) -> list[list[str]]:
    """
    Fetch a tab of a Google Sheet, returning its rows (header row included)
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / f"{gid}.csv"
        get_google_sheet_export_as_csv(key, path, gid=gid)
        with open(path, newline="") as infile:
            return list(csv.reader(infile))


def row_values(row: list[str], columns: dict[str, int]) -> dict[str, str]:
    return {
        name: row[index] if index < len(row) else "" for name, index in columns.items()
    }


class AuthorityLookup:
    """
    Match council names to authority codes, so that renamed councils (eg
    "Sheffield City Region Combined Authority" / "South Yorkshire Combined
    Authority") are treated as the same council.
    """

    def __init__(self):
        self.names_to_codes = {
            row["la-name"].lower(): row["local-authority-code"]
            for _, row in get_authority_mapping().iterrows()
        }

    def code(self, council: str) -> Optional[str]:
        council = council.lower()
        name_versions = [
            council,
            council.replace("council", "").strip(),
            council.replace("- unitary", "").replace("(unitary)", "").strip(),
            council.replace(" combined authority", " mayoral combined authority"),
        ]
        for version in name_versions:
            if version in self.names_to_codes:
                return self.names_to_codes[version]
        return None


class Converter:
    def __init__(self, last_checked: str):
        self.last_checked = last_checked
        self.promises_by_council = defaultdict(list)
        self.blank_rows_by_council = {}

    # --- 2026 sheet ---------------------------------------------------------

    def convert_updated_sheet(self, rows: list[list[str]]):
        columns = find_columns(rows[0], UPDATED_SHEET_COLUMNS, "updated")

        # start at 2, to match the sheet's row numbers
        for row_number, row in enumerate(rows[1:], start=2):
            values = row_values(row, columns)
            council = clean(values["council"])
            if not council:
                continue
            self.convert_updated_row(council, row_number, values)

        for council in set(self.promises_by_council) | set(self.blank_rows_by_council):
            self.tidy_council(council)

    def new_promise(self, council, row_number, values, **kwargs) -> Promise:
        return Promise(
            council=council,
            last_checked=self.last_checked,
            ceuk_checked=clean(values["checked"]),
            notes=clean_notes(values["notes"]),
            source_rows=[f"Updated row {row_number}"],
            **kwargs,
        )

    def convert_updated_row(self, council, row_number, values):
        status = clean(values["status"])
        status_key = status.lower()
        promises = self.promises_by_council[council]

        # Tonbridge and Malling, and Torbay, have the new scope and new target
        # year the wrong way round
        swapped = False
        if looks_like_year(values["new_scope"]) and parse_scope(values["new_target"]):
            values["new_scope"], values["new_target"] = (
                values["new_target"],
                values["new_scope"],
            )
            swapped = True

        old = self.old_promise(council, row_number, values)
        new_specs = parse_scope(values["new_scope"])
        unrecognised_new_scope = bool(clean(values["new_scope"])) and not new_specs
        source_date, date_flag = format_date(values["new_source_date"])

        def make_new(domain, scopes, fallback_to_old: bool) -> Promise:
            """
            Build the promise described by the new columns. If fallback_to_old
            is set, blank new columns are filled in from the old columns.
            """
            promise = self.new_promise(
                council,
                row_number,
                values,
                domain=domain,
                scopes=scopes,
                status=LATEST,
                ceuk_review_outcome=status,
                source_date=source_date,
            )
            year, text, target_flag = parse_target(values["new_target"])
            if year is None and not text and fallback_to_old and old:
                year, text = old.target_date_year, old.target_date_text
                target_flag = None
            promise.target_date_year, promise.target_date_text = year, text
            if target_flag:
                promise.flag(target_flag)

            promise.wording = clean(values["new_wording"])
            if not promise.wording and fallback_to_old and old:
                promise.wording = old.wording

            # take the new source url and name together, so that we don't
            # end up with an old source name next to a new source url
            if clean(values["new_source_url"]):
                promise.source_url = clean(values["new_source_url"])
                promise.source_name = clean(values["new_source_name"])
            elif fallback_to_old and old:
                promise.source_url = old.source_url
                promise.source_name = old.source_name

            if date_flag:
                promise.flag(date_flag)
            if swapped:
                promise.flag(
                    "New scope and new target year were swapped in the original"
                )
            if unrecognised_new_scope:
                promise.flag(f"Unrecognised new scope: '{clean(values['new_scope'])}'")
            if promise.target_date_year is None and not promise.target_date_text:
                promise.flag("No target date")
            if not promise.wording and not promise.source_url:
                promise.flag("No wording or source")
            return promise

        def new_specs_or_old() -> list[tuple[str, str]]:
            if new_specs:
                return new_specs
            if old and old.domain:
                return [(old.domain, old.scopes)]
            return [(UNCLEAR, NOT_SPECIFIED)]

        if status_key in (STILL_CURRENT, WRONG_INITIALLY):
            for domain, scopes in new_specs_or_old():
                promise = make_new(domain, scopes, fallback_to_old=True)
                if not new_specs and not (old and old.domain):
                    promise.flag("No scope given, so domain set to Unclear")
                if status_key == STILL_CURRENT and old and old.domain:
                    if (old.target_date_year, old.target_date_text) != (
                        promise.target_date_year,
                        promise.target_date_text,
                    ):
                        promise.flag(
                            "Marked 'still current' but the target date changed from "
                            f"{old.target_date_year or old.target_date_text or 'blank'} to "
                            f"{promise.target_date_year or promise.target_date_text or 'blank'}"
                        )
                    if old.domain not in (UNCLEAR, domain):
                        promise.flag(
                            f"Marked 'still current' but the domain changed from {old.domain}"
                        )
                if (
                    status_key == WRONG_INITIALLY
                    and old
                    and (old.domain or old.wording)
                ):
                    promise.add_note(
                        "Corrected in CEUK's 2026 review. Previously recorded as: "
                        + old.describe()
                    )
                promises.append(promise)

        elif status_key in (UPDATED_STRONGER, UPDATED_WEAKER):
            if old and old.domain:
                old.status = SUPERSEDED
                promises.append(old)
            for domain, scopes in new_specs_or_old():
                promise = make_new(domain, scopes, fallback_to_old=False)
                if clean(values["scope"]).lower() == NO_PROMISE:
                    promise.flag("Marked as updated, but there was no previous promise")
                promises.append(promise)

        elif status_key in (NEW_TARGET, NEW_AUTHORITY):
            # some rows have the old columns partly filled in, without a
            # source, as a placeholder for the new promise (eg Kingston)
            placeholder = old and old.domain and not old.source_url
            if old and old.domain and not placeholder:
                old.status = SUPERSEDED
                promises.append(old)
                old.flag(
                    "Marked 'new target' but the row already had an original promise"
                )
            specs = new_specs or [(UNCLEAR, NOT_SPECIFIED)]
            for domain, scopes in specs:
                promise = make_new(domain, scopes, fallback_to_old=False)
                if not new_specs:
                    promise.flag("No scope given, so domain set to Unclear")
                if placeholder:
                    promise.flag(
                        "Ignored the original columns, which had no source: "
                        + old.describe()
                    )
                promises.append(promise)

        elif status_key == WITHDRAWN:
            if old and old.domain:
                old.status = STATUS_WITHDRAWN
                # CEUK's "Withdrawn" outcome describes the promise, so it goes
                # on the promise row rather than the withdrawal row
                old.ceuk_review_outcome = status
                promises.append(old)

                # the withdrawal gets its own row, with the domain and scopes
                # of the promise it withdrew
                withdrawal = self.new_promise(
                    council,
                    row_number,
                    values,
                    type=TYPE_WITHDRAWAL,
                    domain=old.domain,
                    scopes=old.scopes,
                    status=LATEST,
                    wording=clean(values["new_wording"]),
                    source_url=clean(values["new_source_url"]),
                    source_name=clean(values["new_source_name"]),
                    source_date=source_date,
                )
                if date_flag:
                    withdrawal.flag(date_flag)
                if new_specs and new_specs[0][0] != old.domain:
                    withdrawal.flag(
                        f"Withdrawn {old.domain} promise, but the new scope says "
                        f"'{clean(values['new_scope'])}'"
                    )
                if not withdrawal.wording and not withdrawal.source_url:
                    withdrawal.flag("No wording or source for the withdrawal")
                promises.append(withdrawal)
            else:
                self.blank_row(council, row_number, values).flag(
                    "Marked withdrawn, but there was no original promise to withdraw"
                )

        elif status_key in (TARGET_MET, TARGET_MISSED):
            self.convert_met_or_missed(
                council, row_number, values, status, old, new_specs, make_new
            )

        elif status_key == NO_PROMISE:
            blank = self.blank_row(council, row_number, values)
            if old and old.domain:
                blank.flag(
                    "Marked 'No Promise', but the row had an original promise: "
                    + old.describe()
                )

        else:
            promise = old or self.blank_row(council, row_number, values)
            promise.status = LATEST if promise.domain else ""
            promise.flag(f"Unrecognised status: '{status}'")
            if promise.domain:
                promises.append(promise)

    def old_promise(self, council, row_number, values) -> Optional[Promise]:
        """
        Build the promise described by the old columns, or None if they're
        blank.
        """
        scope = clean(values["scope"])
        year, text, target_flag = parse_target(values["target"])
        wording = clean(values["wording"])
        source_url = clean(values["source_url"])

        if not any([scope, year, text, wording, source_url]):
            return None

        promise = self.new_promise(
            council,
            row_number,
            values,
            status=LATEST,
            target_date_year=year,
            target_date_text=text,
            wording=wording,
            source_url=source_url,
            source_name=clean(values["source_name"]),
        )
        if target_flag:
            promise.flag(target_flag)

        if scope.lower() == NO_PROMISE:
            if year or text or wording or source_url:
                promise.flag(
                    "Original scope was 'No promise', but it had a target date, wording "
                    "or source"
                )
            return promise

        specs = parse_scope(scope)
        if scope.lower() == "other":
            specs = [(UNCLEAR, NOT_SPECIFIED)]
            promise.flag("Original scope was 'Other', so domain set to Unclear")
        elif not scope:
            specs = [(UNCLEAR, NOT_SPECIFIED)]
            promise.flag("Original promise has no scope, so domain set to Unclear")
        elif not specs:
            specs = [(UNCLEAR, NOT_SPECIFIED)]
            promise.flag(
                f"Unrecognised original scope '{scope}', so domain set to Unclear"
            )
        promise.domain, promise.scopes = specs[0]

        if not wording and not source_url:
            promise.flag("Original promise has no wording or source")
        return promise

    def convert_met_or_missed(
        self, council, row_number, values, status, old, new_specs, make_new
    ):
        promises = self.promises_by_council[council]

        # The promise this judgement is about is the original promise on this
        # row, or (for rows splitting a promise into scopes, like Winchester)
        # the original promise from an earlier row for the same domain
        target = None
        if old and old.domain:
            target = old
            promises.append(target)
        elif new_specs:
            domain = new_specs[0][0]
            for promise in promises:
                if (
                    promise.status == LATEST
                    and promise.domain == domain
                    and promise.scopes == NOT_SPECIFIED
                ):
                    target = promise
                    break

        if target is None:
            # nothing to attach this to, so treat the new columns as the
            # promise itself (eg Warwick's scope 1 & 2 2025 target)
            domain, scopes = (new_specs or [(UNCLEAR, NOT_SPECIFIED)])[0]
            target = make_new(domain, scopes, fallback_to_old=False)
            target.flag(
                f"Marked '{status}', but there was no original promise, so this "
                "promise was built from the new columns"
            )
            promises.append(target)
            return

        # whether the target was met or missed is recorded in the
        # ceuk_review_outcome and notes columns, and the promise stays latest
        if target is not old:
            target.source_rows.append(f"Updated row {row_number}")
            target.add_note(clean_notes(values["notes"]))
            target.ceuk_checked = target.ceuk_checked or clean(values["checked"])

        target.ceuk_review_outcome = join_text(target.ceuk_review_outcome, status, "; ")

    def blank_row(self, council, row_number, values) -> Promise:
        """
        Record a "checked, but no promise found" row for a council
        """
        if council in self.blank_rows_by_council:
            blank = self.blank_rows_by_council[council]
            blank.source_rows.append(f"Updated row {row_number}")
            blank.add_note(clean_notes(values["notes"]))
        else:
            blank = self.new_promise(
                council,
                row_number,
                values,
                ceuk_review_outcome=clean(values["status"]),
            )
            self.blank_rows_by_council[council] = blank
        return blank

    def tidy_council(self, council):
        """
        Merge duplicate promises, flag possible duplicates, and only keep a
        "no promise found" row for councils with no promises at all.
        """
        promises = self.promises_by_council[council]
        tidied = []
        for promise in promises:
            duplicate = next(
                (
                    existing
                    for existing in tidied
                    if existing.same_target(promise) and existing.same_source(promise)
                ),
                None,
            )
            if duplicate is None:
                tidied.append(promise)
            else:
                duplicate.merge(promise)
                # superseded promises are expected to be repeated, when one
                # promise was split into several new ones
                if promise.status != SUPERSEDED:
                    duplicate.flag("Merged duplicate rows")

        for promise in tidied:
            if promise.status != LATEST:
                continue
            others = [
                other
                for other in tidied
                if other is not promise
                and other.status == LATEST
                and (other.domain, other.scopes) == (promise.domain, promise.scopes)
            ]
            if others:
                promise.flag(
                    f"More than one latest {promise.domain} ({promise.scopes}) promise "
                    "for this council"
                )

        self.promises_by_council[council] = tidied

        blank = self.blank_rows_by_council.get(council)
        if blank and tidied:
            # attach anything flagged on the blank row to the real promises
            for message in blank.flags:
                tidied[0].flag(message)
            del self.blank_rows_by_council[council]

    # --- Original sheet -----------------------------------------------------

    def copy_missing_councils(self, rows: list[list[str]], lookup: AuthorityLookup):
        """
        Copy promises from the original sheet for councils that aren't in the
        2026 sheet at all (mostly abolished councils).
        """
        converted = set(self.promises_by_council) | set(self.blank_rows_by_council)
        converted_codes = {lookup.code(council) for council in converted} - {None}

        columns = find_columns(rows[0], ORIGINAL_SHEET_COLUMNS, "original")
        copied = set()
        for row_number, row in enumerate(rows[1:], start=2):
            values = row_values(row, columns)
            council = clean(values["council"])
            if not council or council in converted:
                continue
            code = lookup.code(council)
            if code in converted_codes:
                continue

            year, text, target_flag = parse_target(values["target"])
            promise = Promise(
                council=council,
                target_date_year=year,
                target_date_text=text,
                wording=clean(values["wording"]),
                source_url=clean(values["source_url"]),
                source_name=clean(values["source_name"]),
                notes=clean_notes(values["notes"]),
                source_rows=[f"Original row {row_number}"],
            )
            promise.flag(
                "Copied from the original tab, because the council isn't in the 2026 review"
            )
            if code is None:
                promise.flag("Couldn't match this council to an authority code")
            if target_flag:
                promise.flag(target_flag)

            scope = clean(values["scope"])
            specs = parse_scope(scope)
            if scope.lower() == "other":
                specs = [(UNCLEAR, NOT_SPECIFIED)]
                promise.flag("Original scope was 'Other', so domain set to Unclear")
            if specs:
                promise.domain, promise.scopes = specs[0]
                promise.status = LATEST
            elif scope.lower() != NO_PROMISE:
                promise.flag(f"Unrecognised original scope: '{scope}'")
            if promise.domain:
                self.promises_by_council[council].append(promise)
            else:
                self.blank_rows_by_council.setdefault(council, promise)
            copied.add(council)
        return copied

    # --- Output -------------------------------------------------------------

    def all_rows(self) -> list[Promise]:
        rows = [
            promise
            for promises in self.promises_by_council.values()
            for promise in promises
        ] + list(self.blank_rows_by_council.values())

        for promise in rows:
            # everything with a domain that isn't a withdrawal is a promise;
            # "checked, no promise found" rows have no type
            if promise.domain and not promise.type:
                promise.type = TYPE_PROMISE
            if promise.source_url and not looks_like_url(promise.source_url):
                promise.flag("source_url doesn't look like a URL")

        return sorted(rows, key=lambda promise: promise.sort_key())


class Command(BaseCommand):
    help = (
        "One-off conversion of CEUK's 2026 updated net zero targets Google Sheet "
        "into a CSV with one promise per row"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default=f"{settings.DATA_DIR}/promises-one-per-row.csv",
            help="Path to write the converted CSV to",
        )
        parser.add_argument(
            "--key",
            default=settings.PROMISES_CSV_KEY,
            help="Key of the Google Sheet containing the promises",
        )
        parser.add_argument(
            "--updated-gid",
            default="1595004386",
            help="gid of the 'Updated net zero targets - FINAL' tab",
        )
        parser.add_argument(
            "--original-gid",
            default="0",
            help="gid of the 'Original Net zero targets' tab",
        )
        parser.add_argument(
            "--last-checked",
            default="2026-11",
            help="Value for the last_checked column of rows from CEUK's 2026 review",
        )

    def handle(self, *args, **options):
        updated_rows = fetch_sheet(options["key"], options["updated_gid"])
        original_rows = fetch_sheet(options["key"], options["original_gid"])

        converter = Converter(last_checked=options["last_checked"])
        converter.convert_updated_sheet(updated_rows)
        copied = converter.copy_missing_councils(original_rows, AuthorityLookup())
        rows = converter.all_rows()

        with open(options["output"], "w", newline="") as outfile:
            writer = csv.DictWriter(outfile, fieldnames=OUTPUT_COLUMNS)
            # spaces rather than underscores, to read more naturally in the sheet
            writer.writerow({col: col.replace("_", " ") for col in OUTPUT_COLUMNS})
            for promise in rows:
                writer.writerow(promise.as_row())

        councils = {promise.council for promise in rows}
        statuses = defaultdict(int)
        for promise in rows:
            if promise.type:
                statuses[f"{promise.type}, {promise.status}"] += 1
            else:
                statuses["(no promise found)"] += 1
        flagged = sum(1 for promise in rows if promise.flags)

        self.stdout.write(
            f"Wrote {len(rows)} rows for {len(councils)} councils to {options['output']}"
        )
        for status, count in sorted(statuses.items()):
            self.stdout.write(f"  {status}: {count}")
        self.stdout.write(
            f"Copied {len(copied)} councils from the original tab: {', '.join(sorted(copied))}"
        )
        self.stdout.write(f"{flagged} rows have conversion flags to review")
