from django.test import TestCase, Client
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
