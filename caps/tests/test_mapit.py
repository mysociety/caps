from django.test import TestCase, Client

from unittest.mock import patch

from caps.models import Council

from caps.mapit import MapIt, NotFoundException, BadRequestException

class TestMapitResponses(TestCase):

    @patch('caps.mapit.session')
    def test_postcode_point_to_gss_codes(self, mapit_session):
        mapit_session.get.return_value.json.return_value = {"areas": {"11111": {
            "id": 11111,
            "codes": {"gss": "E14000111", "unit_id": "11111"},
            "name": "Borsetshire Council",
            "country": "E",
            "type": "CTY"
        }}}
        mapit = MapIt()
        actual = mapit.postcode_point_to_gss_codes('BO11AA')
        self.assertEqual(actual, ['E14000111'])

    @patch('caps.mapit.session')
    def test_invalid_postcode(self, mapit_session):
        mapit_session.get.return_value.json.return_value = {'code': 400, 'error': 'Postcode invalid'}
        mapit_session.get.return_value.status_code = 400
        mapit = MapIt()
        with self.assertRaisesMessage(BadRequestException, 'Postcode invalid'):
            actual = mapit.postcode_point_to_gss_codes('BO11AB') # different value to avoid cache

    @patch('caps.mapit.session')
    def test_unknown_postcode(self, mapit_session):
        mapit_session.get.return_value.json.return_value = {'code': 404, 'error': 'Postcode not found'}
        mapit_session.get.return_value.status_code = 404
        mapit = MapIt()
        with self.assertRaisesMessage(NotFoundException, 'Postcode not found'):
            actual = mapit.postcode_point_to_gss_codes('BO11AC') # different value to avoid cache
