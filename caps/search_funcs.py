"""
Functions for use by the semantic search features
"""

import re
from collections import namedtuple
from itertools import groupby
from typing import Optional, NamedTuple

from django.conf import settings
from django.db.models import Q
from haystack.inputs import Exact
from haystack.query import SearchQuerySet

from caps.models import KeyPhrase, KeyPhrasePairWise


highlighter_config = {
    "hl.simple.pre": "<mark>",
    "hl.simple.post": "</mark>",
    "hl.fragsize": 400,
    "hl.snippets": 3,
    "hl.requireFieldMatch": "true",
}

fuller_highlighter_config = {
    "hl.maxAnalyzedChars": 51200,
    "h1.mergeContiguous": "true",
    "hl.simple.pre": "<mark>",
    "hl.simple.post": "</mark>",
    "hl.fragsize": 400,
    "hl.snippets": 5,
    "hl.usePhraseHighlighter": "true",
    "hl.highlightMultiTerm": "true",
    "hl.requireFieldMatch": "true",
}


class KeyPhraseSearch(NamedTuple):
    """
    Holding tuple for keyphrases and their cosine similarity
    """

    keyphrase: str
    cosine_similarity: float
    has_common_word: bool


def phrase_is_somewhere_in_list(phrase: str, list_of_phrases: list[str]) -> bool:
    """
    Check if a phrase is anywhere in a list of phrases
    """
    for p in list_of_phrases:
        if phrase in p:
            return True
    return False


def condense_highlights(
    result: SearchQuerySet, allowed_keywords: list[KeyPhraseSearch] = []
) -> tuple[SearchQuerySet, list[str]]:
    """
    solr's highlighter highlights individual words, even when it's an exact phrase
    here we're just merging adjacent highlights together
    """
    new_result = []
    extracted_highlights = []
    for r in result:
        new_highlights = []
        for s in r.highlighted.get("text", []):
            s = s.replace("</mark> <mark>", " ")
            new_highlights.append(s)
            # get the text that was highlighted
            extracted_highlights.extend(
                [x.lower() for x in re.findall(r"<mark>(.*?)</mark>", s)]
            )
        r.highlighted["text"] = new_highlights
        new_result.append(r)
    result = new_result
    matched_keywords = [
        x
        for x in allowed_keywords
        if phrase_is_somewhere_in_list(x.keyphrase, extracted_highlights)
    ]
    # sort by cosine similarity
    matched_keywords = sorted(
        matched_keywords, key=lambda x: x.cosine_similarity, reverse=True
    )
    matched_keywords = sorted(
        matched_keywords, key=lambda x: x.has_common_word, reverse=False
    )

    extracted_highlights = [x.keyphrase for x in matched_keywords]

    return result, extracted_highlights


def get_semantic_query(
    q: str,
    threshold: float = settings.RELATED_SEARCH_THRESHOLD,
    limit_to_ids: Optional[list[int]] = None,
) -> tuple[Optional[SearchQuerySet], list[KeyPhraseSearch]]:
    """
    Run a semantic search query against the contents of the plan documents
    """

    # get lower case version of q
    q_lower = q.lower()

    # get all the related terms
    all_related = list(KeyPhrase.objects.filter(keyphrase__length__gt=4))
    triggered_keywords = []
    for related in all_related:
        if related.keyphrase.lower() in q.lower():
            triggered_keywords.append(related)

    if not triggered_keywords:
        return None, []

    all_related_lookup = {x.id: x for x in all_related}

    # for each term, we want to get all the related terms (same set_id)
    # and then construct a complex query where the original term is replaced by the new term
    # e.g. if the original query is "housing" and the related term is "housing association"
    # we want to search for "housing association" OR "housing"
    all_alternative_terms = KeyPhrasePairWise.objects.filter(
        word_a_id__in=[x.id for x in triggered_keywords],
        cosine_similarity__gte=threshold,
    )

    # group by word_a_id into a dict
    grouped_related_terms = {
        k: list(v) for k, v in groupby(all_alternative_terms, lambda x: x.word_a_id)
    }

    query_parts = []
    all_related_terms = []

    def get_word_with_cosine(x: KeyPhrasePairWise) -> Optional[KeyPhrase]:
        """
        Get back to the phrase object we already have, but keep the cosine
        from the comparison
        """
        obj = all_related_lookup.get(x.word_b_id, None)
        if obj:
            obj.cosine_similarity = x.cosine_similarity
            obj.has_common_word = x.has_common_word
            return obj

    query_parts = Q(text__iexact=Exact(q_lower))
    for keyword in triggered_keywords:
        # get grouped terms
        keyword_terms = grouped_related_terms.get(keyword.id, [])
        # sort by cosine similarity
        keyword_terms = sorted(
            keyword_terms, key=lambda x: x.cosine_similarity, reverse=True
        )

        # get back to a list of keyphases that we fetched earlier
        related_terms = [get_word_with_cosine(x) for x in keyword_terms]
        related_terms = [x for x in related_terms if x]
        all_related_terms.extend(
            [
                KeyPhraseSearch(
                    keyphrase=x.keyphrase,
                    cosine_similarity=x.cosine_similarity,
                    has_common_word=x.has_common_word,
                )
                for x in related_terms
            ]
        )

        # construct the query
        for term in related_terms:
            alt_text = q_lower.replace(keyword.keyphrase, term.keyphrase)
            query_parts |= Q(text__iexact=Exact(alt_text))
        # run the query
        sqs = SearchQuerySet().filter(query_parts)
    # if given a specific set of documents limit to that
    if limit_to_ids:
        sqs = sqs.filter_and(django_id__in=limit_to_ids)

    all_related_terms = list(set(all_related_terms))

    return sqs, all_related_terms
