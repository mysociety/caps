"""
Importer for related search terms
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import requests
from django.core.management.base import BaseCommand
from tqdm import tqdm

from caps.models import CachedSearch, KeyPhrase, KeyPhrasePairWise, PlanDocument
from caps.search_funcs import (
    condense_highlights,
    fuller_highlighter_config,
    get_semantic_query,
)


def fetch_data():
    """
    Download the data from the cape_ml_search repo
    """

    keyphrase_url = "https://raw.githubusercontent.com/mysociety/cape_ml_search/main/data/final/ml_keyphrases_with_highlights.csv"
    pairwise_url = "https://raw.githubusercontent.com/mysociety/cape_ml_search/main/data/final/ml_keyphrases_pairwise.csv"

    keyphrase_file = requests.get(keyphrase_url, timeout=60)
    pairwise_file = requests.get(pairwise_url, timeout=60)

    Path("data", "ml_keyphrases_with_highlights.csv").write_bytes(
        keyphrase_file.content
    )
    Path("data", "ml_keyphrases_pairwise.csv").write_bytes(pairwise_file.content)


def run_recent_searches(verbose: bool = False):
    """
    Run searches just for documents that were first found in the two weeks
    """
    week_ago = datetime.now() - timedelta(days=14)
    docs = PlanDocument.objects.filter(date_first_found__gte=week_ago)
    ids = [d.id for d in docs]
    print(f"Found {len(ids)} recent documents to update search results")
    run_searches(verbose=verbose, limit_to_ids=ids)


def run_searches(verbose: bool = False, limit_to_ids: Optional[list[int]] = None):
    """
    For each primary related search term, run the search in haystack and save the results
    """
    new_searches = []
    allowed_keyphrases = list(KeyPhrase.valid_keyphrases())
    if verbose:
        print(f"Checking {len(allowed_keyphrases)} keyphrases")
    for keyphrase in tqdm(allowed_keyphrases, disable=not verbose):
        if verbose:
            tqdm.write(f"Running search for {keyphrase.keyphrase}")
        sqs, _ = get_semantic_query(keyphrase.keyphrase, limit_to_ids=limit_to_ids)
        results = sqs.highlight(**fuller_highlighter_config)
        if verbose:
            tqdm.write(f"Found {len(results)} matched documents")

        results, _ = condense_highlights(results, [])

        for r in results:
            doc_id = r.object.id

            # get number of times phrases were found in document
            if "text" in r.highlighted:
                highlighted = " ".join(r.highlighted["text"])
                # count the number of marks
                count = highlighted.count("<mark>")
            else:
                count = 0
            if verbose:
                tqdm.write(f"{doc_id} {count} {keyphrase.keyphrase}")
            if count > 0:
                new_searches.append(
                    CachedSearch(search_term=keyphrase, document_id=doc_id, count=count)
                )

    if limit_to_ids:
        CachedSearch.objects.filter(document_id__in=limit_to_ids).delete()
    else:
        CachedSearch.objects.all().delete()
    CachedSearch.objects.bulk_create(new_searches)


class Command(BaseCommand):
    help = "Import keyphrases and run searches"

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help="Reimports all keyphrases if not present",
        )
        parser.add_argument(
            "--reload-searches",
            action="store_true",
            help="Runs the search against all documents",
        )
        parser.add_argument(
            "--quiet",
            action="store_true",
            help="Do not display progress bars and other output",
        )

    def handle(self, *args, **options):
        get_all = options["all"]
        verbose = not options["quiet"]
        reload_searches = options["reload_searches"]
        if get_all or not KeyPhrase.objects.count():
            if verbose:
                print("Downloading data")
            fetch_data()
            if verbose:
                print("Importing Keyphrases")
            KeyPhrase.populate(quiet=not verbose)
            if verbose:
                print("Importing Keyphrase Pairwise")
            KeyPhrasePairWise.populate(quiet=not verbose)
        if reload_searches or get_all or not CachedSearch.objects.count():
            if verbose:
                print("Running searches")
            run_searches(verbose=verbose)
        else:
            run_recent_searches(verbose=verbose)
