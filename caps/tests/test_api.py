import json
from rest_framework.test import APITestCase
from caps.models import Council, PlanDocument

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
