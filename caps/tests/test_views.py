from django.test import TestCase, Client

from unittest.mock import patch

from django.urls import reverse

from caps.models import Council

class TestPageRenders(TestCase):

    def setUp(self):
        self.client = Client()
        council = Council.objects.create(name='Borsetshire',
                                         slug='borsetshire',
                                         country=Council.ENGLAND)

    def test_home_page(self):
        url = reverse('home')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'home.html')

    def test_council_detail(self):
        url = reverse('council', args=['borsetshire'])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'council_detail.html')

    def test_search_results(self):
        url = reverse('search_results')
        response = self.client.get(url, {'q': 'ev charging'})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'search_results.html')

    def test_council_list(self):
        url = reverse('council_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'council_list.html')


class TestPostcodeSearch(TestCase):

    def setUp(self):
        Council.objects.create(name='Borsetshire',
                               slug='borsetshire',
                               country=Council.ENGLAND,
                               authority_code='BOS',
                               gss_code='E14000111')

        Council.objects.create(name='Borsetshire District',
                               slug='borsetshire-district',
                               country=Council.ENGLAND,
                               authority_code='BOD',
                               gss_code='E14000222')

        felpersham = Council.objects.create(name='Felpersham Combined Authority',
                                            slug='felpersham',
                                            country=Council.ENGLAND,
                                            authority_code='FEL',
                                            gss_code='E14000444')
        Council.objects.create(name='Ambridge',
                               slug='ambridge',
                               country=Council.ENGLAND,
                               authority_code='AMB',
                               gss_code='E14000333',
                               combined_authority=felpersham)



    @patch('caps.mapit.session')
    def test_postcode_to_one_council_redirects_to_council(self, mapit_session):
        mapit_session.get.return_value.json.return_value = {
            "areas": {
                "11111": {
                    "id": 11111,
                    "codes": {"gss": "E14000111", "unit_id": "11111"},
                    "name": "Borsetshire Council",
                    "country": "E",
                    "type": "CTY"
                }
            }
        }
        response = self.client.get('/postcode/?pc=BO11AD', follow=True)
        self.assertRedirects(response, '/councils/borsetshire/')


    @patch('caps.mapit.session')
    def test_postcode_to_two_councils_shows_results(self, mapit_session):
        mapit_session.get.return_value.json.return_value = {
            "areas": {
                "11111": {
                    "id": 11111,
                    "codes": {"gss": "E14000111", "unit_id": "11111"},
                    "name": "Borsetshire Council",
                    "country": "E",
                    "type": "CTY"
                },
                "22222": {
                    "id": 22222,
                    "codes": {"gss": "E14000222", "unit_id": "22222"},
                    "name": "Borsetshire District",
                    "country": "E",
                    "type": "DIS"
                }
            }
        }
        response = self.client.get('/postcode/?pc=BO11AE', follow=True)
        self.assertTemplateUsed(response, 'postcode_results.html')


    @patch('caps.mapit.session')
    def test_postcode_to_council_and_combined_authority_shows_results(self, mapit_session):
        mapit_session.get.return_value.json.return_value = {
            "areas": {
                "33333": {
                    "id": 33333,
                    "codes": {"gss": "E14000333", "unit_id": "33333"},
                    "name": "Ambridge",
                    "country": "E",
                    "type": "DIS"
                }
            }
        }
        response = self.client.get('/postcode/?pc=BO11AF', follow=True)
        self.assertTemplateUsed(response, 'postcode_results.html')
