import json
from django.utils.timezone import make_aware
from datetime import datetime
from rest_framework.test import APITestCase
from caps.models import Council, PlanDocument, SavedSearch

class CouncilsAPITestCase(APITestCase):

    council = None

    def setUp(self):
        self.council = Council.objects.create(name='Borsetshire',
                               slug='borsetshire',
                               country=Council.ENGLAND,
                               authority_code='BOS',
                               gss_code='E14000111')

    def test_basic_council_api(self):
        response = self.client.get('/api/councils/')

        # use json loads as response.data uses an ordered dict so this is a
        # bit more readable
        self.assertEquals(json.loads(response.content),
            [ {
                'authority_type': '',
                'gss_code': 'E14000111',
                'country': 'England',
                'name': 'Borsetshire',
                'plan_count': 0,
                'url': '/councils/borsetshire/',
                'website_url': '',
            } ]
        )

    def test_council_api_plan_count(self):
        plan = PlanDocument.objects.create(
            council=self.council,
            url='https://borsetshire.gov.uk/climate_plan.pdf',
            document_type=PlanDocument.PRE_PLAN,
            scope=PlanDocument.COUNCIL_ONLY
        )

        response = self.client.get('/api/councils/')

        self.assertEquals(json.loads(response.content),
            [ {
                'authority_type': '',
                'gss_code': 'E14000111',
                'country': 'England',
                'name': 'Borsetshire',
                'plan_count': 1,
                'url': '/councils/borsetshire/',
                'website_url': '',
            } ]
        )

    def test_multiple_councils(self):
        Council.objects.create(name='West Borsetshire',
                               slug='west-borsetshire',
                               country=Council.ENGLAND,
                               authority_type='UA',
                               authority_code='WBS',
                               gss_code='E14000112')

        Council.objects.create(name='East Borsetshire',
                               slug='east-borsetshire',
                               country=Council.ENGLAND,
                               website_url="https://east-borsetshire.gov.uk",
                               authority_code='EBS',
                               gss_code='E14000113')

        response = self.client.get('/api/councils/')

        self.assertEquals(json.loads(response.content),
            [ {
                'name': 'Borsetshire',
                'url': '/councils/borsetshire/',
                'website_url': '',
                'gss_code': 'E14000111',
                'country': 'England',
                'authority_type': '',
                'plan_count': 0,
            }, {
                'name': 'East Borsetshire',
                'url': '/councils/east-borsetshire/',
                'website_url': 'https://east-borsetshire.gov.uk',
                'gss_code': 'E14000113',
                'country': 'England',
                'authority_type': '',
                'plan_count': 0,
            }, {
                'name': 'West Borsetshire',
                'url': '/councils/west-borsetshire/',
                'website_url': '',
                'gss_code': 'E14000112',
                'country': 'England',
                'authority_type': 'Unitary Authority',
                'plan_count': 0,
            } ]
        )


class SearchTermAPITest(APITestCase):

    def test_basic_searchterm_api(self):
        SavedSearch.objects.create(
            user_query="query",
            result_count=2
        )

        response = self.client.get('/api/searchterms/')
        self.assertEquals(json.loads(response.content),
            [ {
                'user_query': "query",
                'result_count': 2,
                'times_seen': 1
            } ]
        )

    def test_term_aggregation(self):
        SavedSearch.objects.create(
            user_query="query",
            result_count=2
        )
        SavedSearch.objects.create(
            user_query="query",
            result_count=2
        )

        response = self.client.get('/api/searchterms/')
        self.assertEquals(json.loads(response.content),
            [ {
                'user_query': "query",
                'result_count': 2,
                'times_seen': 2
            } ]
        )

    def test_result_count_filtering(self):
        SavedSearch.objects.create(
            user_query="query",
            result_count=2
        )
        SavedSearch.objects.create(
            user_query="query",
            result_count=2
        )
        SavedSearch.objects.create(
            user_query="another query",
            result_count=1
        )

        response = self.client.get('/api/searchterms/?min_results=2')
        self.assertEquals(json.loads(response.content),
            [ {
                'user_query': "query",
                'result_count': 2,
                'times_seen': 2
            } ]
        )

    def test_seen_count_filtering(self):
        SavedSearch.objects.create(
            user_query="query",
            result_count=2
        )
        SavedSearch.objects.create(
            user_query="query",
            result_count=2
        )
        SavedSearch.objects.create(
            user_query="another query",
            result_count=1
        )

        response = self.client.get('/api/searchterms/?min_count=2')
        self.assertEquals(json.loads(response.content),
            [ {
                'user_query': "query",
                'result_count': 2,
                'times_seen': 2
            } ]
        )

    def test_date_filtering(self):
        created = make_aware(datetime(2021, 1, 4))
        term = SavedSearch.objects.create(
            user_query="query",
            result_count=2
        )
        term.created = created
        term.save()

        created = make_aware(datetime(2021, 1, 1, 10, 10, 10))
        term = SavedSearch.objects.create(
            user_query="query",
            result_count=2
        )
        term.created = created
        term.save()

        created = make_aware(datetime(2021, 1, 2))
        term = SavedSearch.objects.create(
            user_query="other",
            result_count=3
        )
        term.created = created
        term.save()

        response = self.client.get('/api/searchterms/?start_date=2021-01-03')
        self.assertEquals(json.loads(response.content),
            [ {
                'user_query': "query",
                'result_count': 2,
                'times_seen': 1
            } ]
        )

        response = self.client.get('/api/searchterms/?end_date=2021-01-01')
        self.assertEquals(json.loads(response.content),
            [ {
                'user_query': "query",
                'result_count': 2,
                'times_seen': 1
            } ]
        )

        response = self.client.get('/api/searchterms/?start_date=2021-01-02&end_date=2021-01-03')
        self.assertEquals(json.loads(response.content),
            [ {
                'user_query': "other",
                'result_count': 3,
                'times_seen': 1
            } ]
        )

    def test_errors(self):
        response = self.client.get('/api/searchterms/?start_date=21-01-02')
        self.assertEquals(json.loads(response.content),
            {
                'detail': 'start_date must be a valid date with the format YYYY-MM-DD'
            }
        )

        response = self.client.get('/api/searchterms/?start_date=21-01-32')
        self.assertEquals(json.loads(response.content),
            {
                'detail': 'start_date must be a valid date with the format YYYY-MM-DD'
            }
        )

        response = self.client.get('/api/searchterms/?min_count=0')
        self.assertEquals(json.loads(response.content),
            {
                'detail': 'min_count must be an integer greater than 0'
            }
        )

        response = self.client.get('/api/searchterms/?min_count=two')
        self.assertEquals(json.loads(response.content),
            {
                'detail': 'min_count must be an integer greater than 0'
            }
        )

        response = self.client.get('/api/searchterms/?min_results=0')
        self.assertEquals(json.loads(response.content),
            {
                'detail': 'min_results must be an integer greater than 0'
            }
        )

        response = self.client.get('/api/searchterms/?min_results=two')
        self.assertEquals(json.loads(response.content),
            {
                'detail': 'min_results must be an integer greater than 0'
            }
        )
