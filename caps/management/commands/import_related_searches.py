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


def run_recent_searches():
    """
    Run searches just for documents that were first found in the two weeks
    """
    week_ago = datetime.now() - timedelta(days=14)
    docs = PlanDocument.objects.filter(date_first_found__gte=week_ago)
    ids = [d.id for d in docs]
    print(f"Found {len(ids)} recent documents to update search results")
    run_searches(limit_to_ids=ids)


def run_searches(limit_to_ids: Optional[list[int]] = None):
    """
    For each primary related search term, run the search in haystack and save the results
    """
    new_searches = []
    allowed_keyphrases = list(KeyPhrase.valid_keyphrases())
    print(f"Checking {len(allowed_keyphrases)} keyphrases")
    for keyphrase in tqdm(allowed_keyphrases):
        tqdm.write(f"Running search for {keyphrase.keyphrase}")
        sqs, _ = get_semantic_query(keyphrase.keyphrase, limit_to_ids=limit_to_ids)
        results = sqs.highlight(**fuller_highlighter_config)
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

    def handle(self, *args, **options):
        get_all = options["all"]
        reload_searches = options["reload_searches"]
        if get_all or not KeyPhrase.objects.count():
            print("Downloading data")
            fetch_data()
            print("Importing Keyphrases")
            KeyPhrase.populate()
            print("Importing Keyphrase Pairwise")
            KeyPhrasePairWise.populate()
        if reload_searches or get_all or not CachedSearch.objects.count():
            print("Running searches")
            run_searches()
        else:
            run_recent_searches()
