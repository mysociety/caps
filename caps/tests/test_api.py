import json
from datetime import date, datetime

from django.utils.timezone import make_aware
from rest_framework.test import APITestCase

from caps.models import Council, PlanDocument, Promise, SavedSearch


class CouncilsAPITestCase(APITestCase):

    council = None

    def setUp(self):
        self.council = Council.objects.create(
            name="Borsetshire",
            slug="borsetshire",
            country=Council.ENGLAND,
            authority_code="BOS",
            gss_code="E14000111",
        )

    def test_basic_council_api(self):
        response = self.client.get("/api/councils/")

        # use json loads as response.data uses an ordered dict so this is a
        # bit more readable
        self.assertEquals(
            json.loads(response.content),
            [
                {
                    "authority_code": "BOS",
                    "authority_type": "",
                    "carbon_neutral_date": None,
                    "carbon_reduction_commitment": False,
                    "carbon_reduction_statements": "http://testserver/api/councils/BOS/commitments",
                    "declared_emergency": None,
                    "gss_code": "E14000111",
                    "country": "England",
                    "name": "Borsetshire",
                    "plan_count": 0,
                    "document_count": 0,
                    "plans_last_update": None,
                    "url": "/councils/borsetshire/",
                    "website_url": "",
                }
            ],
        )

    def test_council_api_plan_count(self):
        plan = PlanDocument.objects.create(
            council=self.council,
            url="https://borsetshire.gov.uk/climate_plan.pdf",
            document_type=PlanDocument.PRE_PLAN,
            scope=PlanDocument.COUNCIL_ONLY,
        )

        response = self.client.get("/api/councils/")

        self.assertEquals(
            json.loads(response.content),
            [
                {
                    "authority_code": "BOS",
                    "authority_type": "",
                    "carbon_neutral_date": None,
                    "carbon_reduction_commitment": False,
                    "carbon_reduction_statements": "http://testserver/api/councils/BOS/commitments",
                    "declared_emergency": None,
                    "document_count": 1,
                    "gss_code": "E14000111",
                    "country": "England",
                    "name": "Borsetshire",
                    "plan_count": 0,
                    "plans_last_update": date.today().isoformat(),
                    "url": "/councils/borsetshire/",
                    "website_url": "",
                }
            ],
        )

    def test_multiple_councils(self):
        Council.objects.create(
            name="West Borsetshire",
            slug="west-borsetshire",
            country=Council.ENGLAND,
            authority_type="UA",
            authority_code="WBS",
            gss_code="E14000112",
        )

        Council.objects.create(
            name="East Borsetshire",
            slug="east-borsetshire",
            country=Council.ENGLAND,
            authority_type="CC",
            website_url="https://east-borsetshire.gov.uk",
            authority_code="EBS",
            gss_code="E14000113",
        )

        response = self.client.get("/api/councils/")

        self.assertEquals(
            json.loads(response.content),
            [
                {
                    "name": "Borsetshire",
                    "url": "/councils/borsetshire/",
                    "website_url": "",
                    "gss_code": "E14000111",
                    "country": "England",
                    "authority_type": "",
                    "authority_code": "BOS",
                    "plan_count": 0,
                    "document_count": 0,
                    "plans_last_update": None,
                    "carbon_neutral_date": None,
                    "carbon_reduction_commitment": False,
                    "carbon_reduction_statements": "http://testserver/api/councils/BOS/commitments",
                    "declared_emergency": None,
                },
                {
                    "name": "East Borsetshire",
                    "url": "/councils/east-borsetshire/",
                    "website_url": "https://east-borsetshire.gov.uk",
                    "gss_code": "E14000113",
                    "country": "England",
                    "authority_type": "City of London",
                    "authority_code": "EBS",
                    "plan_count": 0,
                    "document_count": 0,
                    "plans_last_update": None,
                    "carbon_neutral_date": None,
                    "carbon_reduction_commitment": False,
                    "carbon_reduction_statements": "http://testserver/api/councils/EBS/commitments",
                    "declared_emergency": None,
                },
                {
                    "name": "West Borsetshire",
                    "url": "/councils/west-borsetshire/",
                    "website_url": "",
                    "gss_code": "E14000112",
                    "country": "England",
                    "authority_type": "Unitary Authority",
                    "authority_code": "WBS",
                    "plan_count": 0,
                    "document_count": 0,
                    "plans_last_update": None,
                    "carbon_neutral_date": None,
                    "carbon_reduction_commitment": False,
                    "carbon_reduction_statements": "http://testserver/api/councils/WBS/commitments",
                    "declared_emergency": None,
                },
            ],
        )

    def test_filtering(self):
        Council.objects.create(
            name="West Borsetshire",
            slug="west-borsetshire",
            country=Council.ENGLAND,
            authority_type="UA",
            authority_code="WBS",
            gss_code="E14000112",
        )

        Council.objects.create(
            name="East Borsetshire",
            slug="east-borsetshire",
            country=Council.ENGLAND,
            authority_type="CTY",
            website_url="https://east-borsetshire.gov.uk",
            authority_code="EBS",
            gss_code="E14000113",
        )

        Council.objects.create(
            name="North Borsetshire",
            slug="north-borsetshire",
            country=Council.SCOTLAND,
            authority_type="MD",
            website_url="https://north-borsetshire.gov.uk",
            authority_code="NBS",
            gss_code="E14000114",
        )

        response = self.client.get("/api/councils/?authority_type=County Council")

        self.assertEquals(
            json.loads(response.content),
            [
                {
                    "name": "East Borsetshire",
                    "url": "/councils/east-borsetshire/",
                    "website_url": "https://east-borsetshire.gov.uk",
                    "gss_code": "E14000113",
                    "country": "England",
                    "authority_type": "County Council",
                    "authority_code": "EBS",
                    "plan_count": 0,
                    "document_count": 0,
                    "plans_last_update": None,
                    "carbon_neutral_date": None,
                    "carbon_reduction_commitment": False,
                    "carbon_reduction_statements": "http://testserver/api/councils/EBS/commitments",
                    "declared_emergency": None,
                }
            ],
        )

        response = self.client.get(
            "/api/councils/?authority_type=County Council,Unitary Authority"
        )

        self.assertEquals(
            json.loads(response.content),
            [
                {
                    "name": "East Borsetshire",
                    "url": "/councils/east-borsetshire/",
                    "website_url": "https://east-borsetshire.gov.uk",
                    "gss_code": "E14000113",
                    "country": "England",
                    "authority_type": "County Council",
                    "authority_code": "EBS",
                    "plan_count": 0,
                    "document_count": 0,
                    "plans_last_update": None,
                    "carbon_neutral_date": None,
                    "carbon_reduction_commitment": False,
                    "carbon_reduction_statements": "http://testserver/api/councils/EBS/commitments",
                    "declared_emergency": None,
                },
                {
                    "name": "West Borsetshire",
                    "url": "/councils/west-borsetshire/",
                    "website_url": "",
                    "gss_code": "E14000112",
                    "country": "England",
                    "authority_type": "Unitary Authority",
                    "authority_code": "WBS",
                    "plan_count": 0,
                    "document_count": 0,
                    "plans_last_update": None,
                    "carbon_neutral_date": None,
                    "carbon_reduction_commitment": False,
                    "carbon_reduction_statements": "http://testserver/api/councils/WBS/commitments",
                    "declared_emergency": None,
                },
            ],
        )

        response = self.client.get("/api/councils/?country=Scotland")

        self.assertEquals(
            json.loads(response.content),
            [
                {
                    "name": "North Borsetshire",
                    "url": "/councils/north-borsetshire/",
                    "website_url": "https://north-borsetshire.gov.uk",
                    "gss_code": "E14000114",
                    "country": "Scotland",
                    "authority_type": "Metropolitan District",
                    "authority_code": "NBS",
                    "plan_count": 0,
                    "document_count": 0,
                    "plans_last_update": None,
                    "carbon_neutral_date": None,
                    "carbon_reduction_commitment": False,
                    "carbon_reduction_statements": "http://testserver/api/councils/NBS/commitments",
                    "declared_emergency": None,
                }
            ],
        )


class PromisesAPITest(APITestCase):
    def setUp(self):
        self.council_bors = Council.objects.create(
            name="Borsetshire",
            slug="borsetshire",
            country=Council.ENGLAND,
            authority_code="BOS",
            gss_code="E14000111",
        )

        self.council_wbs = Council.objects.create(
            name="West Borsetshire",
            slug="west-borsetshire",
            country=Council.ENGLAND,
            authority_type="UA",
            authority_code="WBS",
            gss_code="E14000112",
        )

    def test_council_with_commitment(self):
        commitment = Promise.objects.create(
            council=self.council_bors,
            target_year=2035,
            source="https://example.com/promise.pdf",
            source_name="Borsetshire Climate Plan",
            text="Carbon Neutral by 2035",
            scope=1,
            has_promise=True,
        )

        response = self.client.get("/api/councils/")

        self.assertEquals(
            json.loads(response.content),
            [
                {
                    "name": "Borsetshire",
                    "url": "/councils/borsetshire/",
                    "website_url": "",
                    "gss_code": "E14000111",
                    "country": "England",
                    "authority_type": "",
                    "authority_code": "BOS",
                    "plan_count": 0,
                    "document_count": 0,
                    "plans_last_update": None,
                    "carbon_neutral_date": 2035,
                    "carbon_reduction_commitment": True,
                    "carbon_reduction_statements": "http://testserver/api/councils/BOS/commitments",
                    "declared_emergency": None,
                },
                {
                    "name": "West Borsetshire",
                    "url": "/councils/west-borsetshire/",
                    "website_url": "",
                    "gss_code": "E14000112",
                    "country": "England",
                    "authority_type": "Unitary Authority",
                    "authority_code": "WBS",
                    "plan_count": 0,
                    "document_count": 0,
                    "plans_last_update": None,
                    "carbon_neutral_date": None,
                    "carbon_reduction_commitment": False,
                    "carbon_reduction_statements": "http://testserver/api/councils/WBS/commitments",
                    "declared_emergency": None,
                },
            ],
        )

        response = self.client.get("/api/councils/BOS/commitments")
        self.assertEquals(
            json.loads(response.content),
            [
                {
                    "council": "http://testserver/api/councils/BOS/",
                    "has_promise": True,
                    "target_year": 2035,
                    "scope": "Council only",
                    "text": "Carbon Neutral by 2035",
                    "source": "https://example.com/promise.pdf",
                    "source_name": "Borsetshire Climate Plan",
                }
            ],
        )


class SearchTermAPITest(APITestCase):
    def test_no_results(self):
        SavedSearch.objects.create(user_query="query", result_count=2)

        response = self.client.get("/api/searchterms/")
        self.assertEquals(
            json.loads(response.content),
            {"count": 0, "next": None, "previous": None, "results": []},
        )

    def test_term_aggregation(self):
        for x in range(7):
            SavedSearch.objects.create(user_query="query", result_count=2)

        response = self.client.get("/api/searchterms/")
        self.assertEquals(
            json.loads(response.content),
            {
                "count": 1,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "user_query": "query",
                        "council_restriction": "",
                        "result_count": 2,
                        "times_seen": 7,
                    }
                ],
            },
        )

    def test_result_count_filtering(self):
        for x in range(6):
            SavedSearch.objects.create(user_query="query", result_count=2)
        for x in range(5):
            SavedSearch.objects.create(user_query="another query", result_count=1)

        response = self.client.get("/api/searchterms/?min_results=2")
        self.assertEquals(
            json.loads(response.content),
            {
                "count": 1,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "user_query": "query",
                        "council_restriction": "",
                        "result_count": 2,
                        "times_seen": 6,
                    }
                ],
            },
        )

    def test_seen_count_filtering(self):
        for x in range(6):
            SavedSearch.objects.create(user_query="query", result_count=2)
        for x in range(5):
            SavedSearch.objects.create(user_query="another query", result_count=1)

        response = self.client.get("/api/searchterms/?min_count=6")
        self.assertEquals(
            json.loads(response.content),
            {
                "count": 1,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "user_query": "query",
                        "council_restriction": "",
                        "result_count": 2,
                        "times_seen": 6,
                    }
                ],
            },
        )

    def test_date_filtering(self):
        created = make_aware(datetime(2021, 1, 4))
        for x in range(5):
            term = SavedSearch.objects.create(user_query="query", result_count=2)
            term.created = created
            term.save()

        created = make_aware(datetime(2021, 1, 1, 10, 10, 10))
        for x in range(6):
            term = SavedSearch.objects.create(user_query="query", result_count=2)
            term.created = created
            term.save()

        created = make_aware(datetime(2021, 1, 2))
        for x in range(5):
            term = SavedSearch.objects.create(user_query="other", result_count=3)
            term.created = created
            term.save()

        response = self.client.get("/api/searchterms/?start_date=2021-01-03")
        self.assertEquals(
            json.loads(response.content),
            {
                "count": 1,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "user_query": "query",
                        "council_restriction": "",
                        "result_count": 2,
                        "times_seen": 5,
                    }
                ],
            },
        )

        response = self.client.get("/api/searchterms/?end_date=2021-01-01")
        self.assertEquals(
            json.loads(response.content),
            {
                "count": 1,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "user_query": "query",
                        "council_restriction": "",
                        "result_count": 2,
                        "times_seen": 6,
                    }
                ],
            },
        )

        response = self.client.get(
            "/api/searchterms/?start_date=2021-01-02&end_date=2021-01-03"
        )
        self.assertEquals(
            json.loads(response.content),
            {
                "count": 1,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "user_query": "other",
                        "council_restriction": "",
                        "result_count": 3,
                        "times_seen": 5,
                    }
                ],
            },
        )

    def test_combine_filters(self):
        created = make_aware(datetime(2021, 1, 4))
        for x in range(8):
            term = SavedSearch.objects.create(user_query="query", result_count=2)
            term.created = created
            term.save()

        for x in range(5):
            term = SavedSearch.objects.create(user_query="other query", result_count=5)
            term.created = created
            term.save()

        created = make_aware(datetime(2021, 1, 1, 10, 10, 10))
        for x in range(7):
            term = SavedSearch.objects.create(user_query="query", result_count=2)
            term.created = created
            term.save()

        for x in range(6):
            term = SavedSearch.objects.create(user_query="other query", result_count=5)
            term.created = created
            term.save()

        for x in range(5):
            term = SavedSearch.objects.create(
                user_query="yet another query", result_count=3
            )
            term.created = created
            term.save()

        response = self.client.get(
            "/api/searchterms/?min_count=7&start_date=2021-01-03"
        )
        self.assertEquals(
            json.loads(response.content),
            {
                "count": 1,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "user_query": "query",
                        "council_restriction": "",
                        "result_count": 2,
                        "times_seen": 8,
                    }
                ],
            },
        )

        response = self.client.get(
            "/api/searchterms/?min_results=3&start_date=2021-01-03"
        )
        self.assertEquals(
            json.loads(response.content),
            {
                "count": 1,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "user_query": "other query",
                        "council_restriction": "",
                        "result_count": 5,
                        "times_seen": 5,
                    }
                ],
            },
        )

        response = self.client.get("/api/searchterms/?min_results=4&min_count=6")
        self.assertEquals(
            json.loads(response.content),
            {
                "count": 1,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "user_query": "other query",
                        "council_restriction": "",
                        "result_count": 5,
                        "times_seen": 11,
                    }
                ],
            },
        )

        response = self.client.get("/api/searchterms/?min_count=7&end_date=2021-01-03")
        self.assertEquals(
            json.loads(response.content),
            {
                "count": 1,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "user_query": "query",
                        "council_restriction": "",
                        "result_count": 2,
                        "times_seen": 7,
                    }
                ],
            },
        )

        response = self.client.get(
            "/api/searchterms/?min_results=4&end_date=2021-01-03"
        )
        self.assertEquals(
            json.loads(response.content),
            {
                "count": 1,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "user_query": "other query",
                        "council_restriction": "",
                        "result_count": 5,
                        "times_seen": 6,
                    }
                ],
            },
        )

        response = self.client.get(
            "/api/searchterms/?min_results=3&min_count=6&end_date=2021-01-03"
        )
        self.assertEquals(
            json.loads(response.content),
            {
                "count": 1,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "user_query": "other query",
                        "council_restriction": "",
                        "result_count": 5,
                        "times_seen": 6,
                    }
                ],
            },
        )

    def test_errors(self):
        response = self.client.get("/api/searchterms/?start_date=21-01-02")
        self.assertEquals(
            json.loads(response.content),
            {"detail": "start_date must be a valid date with the format YYYY-MM-DD"},
        )

        response = self.client.get("/api/searchterms/?start_date=21-01-32")
        self.assertEquals(
            json.loads(response.content),
            {"detail": "start_date must be a valid date with the format YYYY-MM-DD"},
        )

        response = self.client.get("/api/searchterms/?min_count=3")
        self.assertEquals(
            json.loads(response.content),
            {"detail": "min_count must be an integer greater than or equal to 5"},
        )

        response = self.client.get("/api/searchterms/?min_count=two")
        self.assertEquals(
            json.loads(response.content),
            {"detail": "min_count must be an integer greater than or equal to 5"},
        )

        response = self.client.get("/api/searchterms/?min_results=0")
        self.assertEquals(
            json.loads(response.content),
            {"detail": "min_results must be an integer greater than or equal to 1"},
        )

        response = self.client.get("/api/searchterms/?min_results=two")
        self.assertEquals(
            json.loads(response.content),
            {"detail": "min_results must be an integer greater than or equal to 1"},
        )
