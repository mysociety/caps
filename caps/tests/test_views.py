from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse

from caps.models import Council, EmergencyDeclaration, PlanDocument, Promise
from scoring.models import PlanYear


class TestPageRenders(TestCase):
    def setUp(self):
        self.client = Client()
        council = Council.objects.create(
            name="Borsetshire", slug="borsetshire", country=Council.ENGLAND
        )

        PlanYear.objects.create(year=2023, is_current=True)

    def test_home_page(self):
        url = reverse("home")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "caps/home.html")

    def test_council_detail(self):
        url = reverse("council", args=["borsetshire"])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "caps/council_detail.html")

    @patch("caps.forms.HighlightedSearchForm.search")
    def test_search_results(self, mock_search):
        mock_search.return_value = [], []
        url = reverse("search_results")
        response = self.client.get(url, {"q": "ev charging"})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "caps/search_results.html")

    def test_council_list(self):
        url = reverse("council_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "caps/council_list.html")


class TestPostcodeSearch(TestCase):
    def setUp(self):
        Council.objects.create(
            name="Borsetshire",
            slug="borsetshire",
            country=Council.ENGLAND,
            authority_code="BOS",
            gss_code="E14000111",
        )

        Council.objects.create(
            name="Borsetshire District",
            slug="borsetshire-district",
            country=Council.ENGLAND,
            authority_code="BOD",
            gss_code="E14000222",
        )

        felpersham = Council.objects.create(
            name="Felpersham Combined Authority",
            slug="felpersham",
            country=Council.ENGLAND,
            authority_code="FEL",
            gss_code="E14000444",
        )
        Council.objects.create(
            name="Ambridge",
            slug="ambridge",
            country=Council.ENGLAND,
            authority_code="AMB",
            gss_code="E14000333",
            combined_authority=felpersham,
        )

        PlanYear.objects.create(year=2023, is_current=True)

    @patch("caps.mapit.session")
    def test_postcode_to_one_council_redirects_to_council(self, mapit_session):
        mapit_session.get.return_value.json.return_value = {
            "areas": {
                "11111": {
                    "id": 11111,
                    "codes": {"gss": "E14000111", "unit_id": "11111"},
                    "name": "Borsetshire Council",
                    "country": "E",
                    "type": "CTY",
                }
            }
        }
        response = self.client.get("/location/?pc=BO11AD", follow=True)
        self.assertRedirects(response, "/councils/borsetshire/")

    @patch("caps.mapit.session")
    def test_postcode_to_two_councils_shows_results(self, mapit_session):
        mapit_session.get.return_value.json.return_value = {
            "areas": {
                "11111": {
                    "id": 11111,
                    "codes": {"gss": "E14000111", "unit_id": "11111"},
                    "name": "Borsetshire Council",
                    "country": "E",
                    "type": "CTY",
                },
                "22222": {
                    "id": 22222,
                    "codes": {"gss": "E14000222", "unit_id": "22222"},
                    "name": "Borsetshire District",
                    "country": "E",
                    "type": "DIS",
                },
            }
        }
        response = self.client.get("/location/?pc=BO11AE", follow=True)
        self.assertTemplateUsed(response, "caps/location_results.html")

    @patch("caps.mapit.session")
    def test_postcode_to_council_and_combined_authority_shows_results(
        self, mapit_session
    ):
        mapit_session.get.return_value.json.return_value = {
            "areas": {
                "33333": {
                    "id": 33333,
                    "codes": {"gss": "E14000333", "unit_id": "33333"},
                    "name": "Ambridge",
                    "country": "E",
                    "type": "DIS",
                }
            }
        }
        response = self.client.get("/location/?pc=BO11AF", follow=True)
        self.assertTemplateUsed(response, "caps/location_results.html")

    def test_empty_submission_shows_results_page(self):
        response = self.client.get("/location/?pc=")
        self.assertTemplateUsed(response, "caps/location_results.html")


class TestCouncilDetailPage(TestCase):
    promise = None

    def setUp(self):
        council = Council.objects.create(
            name="Borsetshire",
            slug="borsetshire",
            country=Council.ENGLAND,
            authority_code="BOS",
            gss_code="E14000111",
        )

        self.promise = Promise.objects.create(
            council=council,
            has_promise=True,
            text="this is a promise",
            source_name="council website",
            source="http://borsetshire.gov.uk/promise/",
            target_year="2045",
        )

        PlanYear.objects.create(year=2023, is_current=True)

    def test_council_has_promise(self):
        url = reverse("council", args=["borsetshire"])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertRegex(response.content, rb"this is a promise")

    def test_council_past_promises_not_shown(self):
        Promise.objects.create(
            council=self.promise.council,
            has_promise=True,
            text="this is a superseded promise",
            source="http://borsetshire.gov.uk/old-promise/",
            target_year="2050",
            status=Promise.SUPERSEDED,
        )
        Promise.objects.create(
            council=self.promise.council,
            has_promise=True,
            text="this is a withdrawn promise",
            source="http://borsetshire.gov.uk/withdrawn-promise/",
            target_year="2030",
            status=Promise.WITHDRAWN,
        )
        url = reverse("council", args=["borsetshire"])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["promises"]), [self.promise])
        self.assertRegex(response.content, rb"this is a promise")
        self.assertNotRegex(response.content, rb"superseded promise")
        self.assertNotRegex(response.content, rb"withdrawn promise")

    def test_council_has_no_promise(self):
        self.promise.has_promise = False
        self.promise.save()
        url = reverse("council", args=["borsetshire"])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertRegex(
            response.content,
            rb"We couldn\xe2\x80\x99t find any climate pledges from this council",
        )

    def test_council_no_promise_data(self):
        self.promise.delete()
        url = reverse("council", args=["borsetshire"])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertRegex(
            response.content,
            rb"checked whether this council has made any climate pledges",
        )


class TestCouncilListPage(TestCase):
    def setUp(self):
        plan_council = Council.objects.create(
            name="Borsetshire",
            slug="borsetshire",
            authority_code="BORS",
            gss_code="E00000001",
            country=Council.ENGLAND,
        )
        plan = PlanDocument.objects.create(
            document_type=PlanDocument.ACTION_PLAN,
            council=plan_council,
            url="http://example.com",
            url_hash="xxxxxxx",
            file_type="PDF",
        )
        not_plan_for_plan_council = PlanDocument.objects.create(
            document_type=PlanDocument.CLIMATE_STRATEGY,
            council=plan_council,
            url="http://example.org",
            url_hash="xxxxxxy",
            file_type="PDF",
        )
        no_plan_council = Council.objects.create(
            name="Setborshire",
            slug="Setborshire",
            gss_code="E00000002",
            authority_code="SBOR",
            country=Council.ENGLAND,
        )
        promise_first = Promise.objects.create(
            council=no_plan_council,
            target_year=2030,
        )
        promise_second = Promise.objects.create(
            council=no_plan_council,
            target_year=2050,
        )
        # past promises, which shouldn't count
        Promise.objects.create(
            council=no_plan_council,
            domain=Promise.WHOLE_AREA,
            target_year=2025,
            status=Promise.SUPERSEDED,
        )
        Promise.objects.create(
            council=no_plan_council,
            domain=Promise.COUNCIL_OPERATIONS,
            target_year=2025,
            status=Promise.WITHDRAWN,
        )
        Promise.objects.create(
            council=no_plan_council,
            domain=Promise.COUNCIL_OPERATIONS,
            type=Promise.WITHDRAWAL,
        )

        non_plan_doc_council = Council.objects.create(
            name="West Borsetshire",
            slug="west_borsetshire",
            gss_code="E00000003",
            authority_code="WBOR",
            country=Council.ENGLAND,
        )

        not_plan = PlanDocument.objects.create(
            document_type=PlanDocument.CLIMATE_STRATEGY,
            council=non_plan_doc_council,
            url="http://example.net",
            url_hash="xxxxxxz",
            file_type="PDF",
        )
        declaration = EmergencyDeclaration.objects.create(
            council=non_plan_doc_council,
            date_declared="2020-04-20",
        )

    def test_council_list(self):
        url = reverse("council_list")
        response = self.client.get(url)
        context = response.context
        councils = context["filter"].qs

        self.assertEqual(councils.count(), 3)
        councils = councils.values(
            "num_plans", "name", "has_promise", "earliest_promise", "declared_emergency"
        )

        self.assertEqual(councils[0]["name"], "Borsetshire")
        self.assertEqual(councils[0]["num_plans"], 1)
        self.assertEqual(councils[0]["has_promise"], 0)
        self.assertEqual(councils[0]["earliest_promise"], None)
        self.assertEqual(councils[0]["declared_emergency"], None)

        self.assertEqual(councils[1]["name"], "Setborshire")
        self.assertEqual(councils[1]["num_plans"], None)
        self.assertEqual(councils[1]["has_promise"], 2)
        self.assertEqual(councils[1]["earliest_promise"], 2030)
        self.assertEqual(councils[1]["declared_emergency"], None)

        self.assertEqual(councils[2]["name"], "West Borsetshire")
        self.assertEqual(councils[2]["num_plans"], None)
        self.assertEqual(councils[2]["has_promise"], 0)
        self.assertEqual(councils[2]["earliest_promise"], None)
        self.assertEqual(
            councils[2]["declared_emergency"].strftime("%Y-%m-%d"), "2020-04-20"
        )

    def test_council_list_ignores_past_promises_by_domain(self):
        response = self.client.get(reverse("council_list"))
        council = (
            response.context["filter"]
            .qs.values(
                "has_promise_area",
                "has_promise_council",
                "earliest_promise_area",
                "earliest_promise_council",
            )
            .get(name="Setborshire")
        )
        self.assertEqual(
            council,
            {
                "has_promise_area": 0,
                "has_promise_council": 0,
                "earliest_promise_area": None,
                "earliest_promise_council": None,
            },
        )

    def test_council_list_promise_filter(self):
        response = self.client.get(
            reverse("council_list"), {"promise_combined": "2025"}
        )
        self.assertEqual(response.context["filter"].qs.count(), 0)

        response = self.client.get(
            reverse("council_list"), {"promise_combined": "2030"}
        )
        names = [c.name for c in response.context["filter"].qs]
        self.assertEqual(names, ["Setborshire"])

    def test_council_list_sort_by_promise_year(self):
        # sorting by a promise join used to list councils once per promise
        response = self.client.get(reverse("council_list"), {"sort": "promise_year"})
        names = [c.name for c in response.context["filter"].qs]
        self.assertEqual(names[0], "Setborshire")
        self.assertEqual(
            sorted(names), ["Borsetshire", "Setborshire", "West Borsetshire"]
        )


class TestSearchPage(TestCase):
    def test_search_results_detects_postcode(self):
        url = reverse("search_results")
        response = self.client.get(url, {"q": "EH99 1SP"})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "caps/search_results.html")
        self.assertRegex(response.content, rb"Looking for your local council")


class TestMarkDownView(TestCase):
    def test_page_works(self):
        url = reverse("content", args=("mrp",))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_missing_template_404(self):
        url = reverse("content", args=("missing-template",))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
