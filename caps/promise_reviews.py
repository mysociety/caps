"""
Group councils by the outcome of CE UK's 2026 review of their promises
(Promise.review_outcome_2026), for the targets page.

TEMPORARY, like Promise.review_outcome_2026 itself.
"""

from dataclasses import dataclass, field

from caps.models import Council, Promise

# List of tuples: review outcome, category slug, heading, description
CATEGORIES = [
    (
        Promise.REVIEW_2026_STRONGER,
        "stronger",
        "Stronger targets",
        "Councils that have brought their net zero target forward, or widened it.",
    ),
    (
        Promise.REVIEW_2026_WEAKER,
        "weaker",
        "Weaker targets",
        "Councils that have pushed their net zero target back, or narrowed it.",
    ),
    (
        Promise.REVIEW_2026_NEW,
        "new",
        "New targets",
        "Councils that have set a net zero target where they didn’t have one before.",
    ),
    (
        Promise.REVIEW_2026_WITHDRAWN,
        "withdrawn",
        "Withdrawn targets",
        "Councils that have withdrawn a net zero target, without replacing it.",
    ),
    (
        Promise.REVIEW_2026_MISSED,
        "missed",
        "Missed targets",
        "Councils whose target date has passed, without them setting a new one.",
    ),
    (
        Promise.REVIEW_2026_UNCHANGED,
        "unchanged",
        "Unchanged targets",
        "Councils whose net zero target is the same as before.",
    ),
]

# Categories that compare a council's past promises with its latest ones
BEFORE_AND_AFTER = [
    Promise.REVIEW_2026_STRONGER,
    Promise.REVIEW_2026_WEAKER,
    Promise.REVIEW_2026_NEW,
    Promise.REVIEW_2026_WITHDRAWN,
]


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
    review_outcome_2026: int
    slug: str
    title: str
    description: str
    entries: list = field(default_factory=list)

    @property
    def has_before_and_after(self) -> bool:
        return self.review_outcome_2026 in BEFORE_AND_AFTER


def review_categories() -> list[ReviewCategory]:
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
    promises_by_council = {}
    for promise in Promise.objects.select_related("council").in_display_order(
        "council__name", "council_id"
    ):
        promises_by_council.setdefault(promise.council, []).append(promise)

    categories = {
        review_outcome_2026: ReviewCategory(
            review_outcome_2026, slug, title, description
        )
        for review_outcome_2026, slug, title, description in CATEGORIES
    }
    for council, promises in promises_by_council.items():
        reviewed = {}
        for promise in promises:
            if promise.review_outcome_2026:
                reviewed.setdefault(promise.review_outcome_2026, []).append(promise)

        for review_outcome_2026, reviewed_promises in reviewed.items():
            entry = ReviewEntry(council)
            domains = {promise.domain for promise in reviewed_promises}
            if review_outcome_2026 == Promise.REVIEW_2026_WITHDRAWN:
                entry.before = reviewed_promises
                entry.after = [
                    promise
                    for promise in promises
                    if promise.type == Promise.WITHDRAWAL and promise.domain in domains
                ]
            else:
                entry.after = reviewed_promises
                if review_outcome_2026 in BEFORE_AND_AFTER:
                    superseded = [
                        promise
                        for promise in promises
                        if promise.status == Promise.SUPERSEDED
                    ]
                    entry.before = [
                        promise for promise in superseded if promise.domain in domains
                    ] or superseded
            categories[review_outcome_2026].entries.append(entry)

    return list(categories.values())
