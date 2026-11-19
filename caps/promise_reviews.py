"""
Temporary functions to deal with CEUK's 2026 review of promises.

I'm not sure whether we want to include the CEUK stronger/weaker/etc change
descriptions in the Promise model. So for now, the import script writes them
to settings.PROMISE_REVIEWS_JSON, and these functions read them back out again
and zip them up with the Promises from the database.

TODO: Incorporate these into Promise views/models, or delete it all.
"""

import json
import os
from dataclasses import dataclass, field
from typing import Optional

from django.conf import settings

from caps.models import Council, Promise

# List of tuples: category slug, heading, description
CATEGORIES = [
    (
        "stronger",
        "Stronger targets",
        "Councils that have brought their net zero target forward, or widened it.",
    ),
    (
        "weaker",
        "Weaker targets",
        "Councils that have pushed their net zero target back, or narrowed it.",
    ),
    (
        "new",
        "New targets",
        "Councils that have set a net zero target where they didn’t have one before.",
    ),
    (
        "withdrawn",
        "Withdrawn targets",
        "Councils that have withdrawn a net zero target, without replacing it.",
    ),
    (
        "missed",
        "Missed targets",
        "Councils whose target date has passed, without them setting a new one.",
    ),
    (
        "unchanged",
        "Unchanged targets",
        "Councils whose net zero target is the same as before.",
    ),
]

# Categories that compare a council's past promises with its latest ones
BEFORE_AND_AFTER = ["stronger", "weaker", "new", "withdrawn"]

_cache = {}


def outcome_category(outcome: str) -> Optional[str]:
    """
    Return the category slug for one of CE UK's review outcomes, or None
    """
    outcome = outcome.strip().lower()
    if "stronger" in outcome:
        return "stronger"
    if "weaker" in outcome:
        return "weaker"
    # "New target", "New authority - new target"
    if "new target" in outcome:
        return "new"
    if outcome == "withdrawn":
        return "withdrawn"
    # "Target missed - no further target set", "Target met; Target missed..."
    if "missed" in outcome:
        return "missed"
    # "Target still current", "Wrong initially - target still current"
    if "still current" in outcome:
        return "unchanged"
    return None


def write_review_outcomes(outcomes: dict[int, str], path=None):
    path = path or settings.PROMISE_REVIEWS_JSON
    with open(path, "w") as f:
        json.dump({str(pk): outcome for pk, outcome in outcomes.items()}, f, indent=1)


def load_review_outcomes(path=None) -> Optional[dict[int, str]]:
    """
    Return a dict of promise id to CE UK review outcome, or None if there's no
    file. The file is only re-read when it changes.
    """
    path = path or settings.PROMISE_REVIEWS_JSON
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return None

    cached = _cache.get(path)
    if cached is None or cached[0] != mtime:
        with open(path) as f:
            outcomes = {int(pk): outcome for pk, outcome in json.load(f).items()}
        _cache[path] = (mtime, outcomes)
    return _cache[path][1]


def describe_targets(promises, with_domains=False) -> str:
    """
    eg: "2030, 2045", or "Whole area 2030", for the promises (not withdrawals)
    in a list
    """
    targets = []
    for promise in promises:
        if promise.type != Promise.PROMISE:
            continue
        target = str(promise.target_year or promise.target_text or "no date")
        if with_domains and promise.domain:
            target = f"{promise.get_domain_display()} {target}"
        if target not in targets:
            targets.append(target)
    return ", ".join(targets)


@dataclass
class ReviewEntry:
    council: Council
    before: list = field(default_factory=list)
    after: list = field(default_factory=list)

    @property
    def summary(self) -> str:
        """
        eg: "Whole area 2030 → Council operations 2030", "2030 → withdrawn",
        or just "2035".
        """
        with_domains = bool(self.before) and {p.domain for p in self.before} != {
            p.domain for p in self.after if p.type == Promise.PROMISE
        }
        before = describe_targets(self.before, with_domains)
        after = describe_targets(self.after, with_domains) or "withdrawn"
        if before:
            return f"{before} → {after}"
        return after


@dataclass
class ReviewCategory:
    slug: str
    title: str
    description: str
    entries: list = field(default_factory=list)

    @property
    def has_before_and_after(self) -> bool:
        return self.slug in BEFORE_AND_AFTER


def review_categories() -> Optional[list[ReviewCategory]]:
    """
    Group councils by the outcome of CE UK's review of their promises. A
    council can be in more than one category, eg: if it strengthened its
    council operations target and weakened its whole area one.

    For stronger, weaker and new targets, "after" is the reviewed promises, and
    "before" is the council's superseded promises in the same domains (or in
    any domain, if there are none, eg: when a target was narrowed from the
    whole area to council operations). For withdrawn targets, "before" is the
    withdrawn promises, and "after" is the withdrawals in the same domains.
    Missed and unchanged targets only have "after".
    """
    outcomes = load_review_outcomes()
    if outcomes is None:
        return None

    promises_by_council = {}
    for promise in Promise.objects.select_related("council").in_display_order(
        "council__name", "council_id"
    ):
        promises_by_council.setdefault(promise.council, []).append(promise)

    categories = {
        slug: ReviewCategory(slug, title, description)
        for slug, title, description in CATEGORIES
    }
    for council, promises in promises_by_council.items():
        reviewed = {}
        for promise in promises:
            category = outcome_category(outcomes.get(promise.pk, ""))
            if category:
                reviewed.setdefault(category, []).append(promise)

        for category, reviewed_promises in reviewed.items():
            entry = ReviewEntry(council)
            domains = {promise.domain for promise in reviewed_promises}
            if category == "withdrawn":
                entry.before = reviewed_promises
                entry.after = [
                    promise
                    for promise in promises
                    if promise.type == Promise.WITHDRAWAL and promise.domain in domains
                ]
            else:
                entry.after = reviewed_promises
                if category in BEFORE_AND_AFTER:
                    superseded = [
                        promise
                        for promise in promises
                        if promise.status == Promise.SUPERSEDED
                    ]
                    entry.before = [
                        promise for promise in superseded if promise.domain in domains
                    ] or superseded
            categories[category].entries.append(entry)

    return list(categories.values())
